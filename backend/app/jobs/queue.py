"""Очередь обработки (OCR/TZ §8.1 §10.4): job-таблица, sync-воркер, отмена."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from app.db.models import Document, Job


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def enqueue(eng, document_id: str) -> str:
    from app.db.session import SessionLocal

    job_id = str(uuid.uuid4())
    with SessionLocal(eng) as s:
        s.add(Job(id=job_id, document_id=document_id, type="process",
                  status="queued", progress=0,
                  started_at=_now_iso()))
        s.commit()
    worker = threading.Thread(target=_process, args=(eng, job_id), daemon=True)
    worker.start()
    return job_id


def cancel(eng, job_id: str) -> None:
    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        job = s.get(Job, job_id)
        if job is None or job.status in ("done", "error", "canceled"):
            return
        job.status = "canceled"
        job.finished_at = _now_iso()
        doc = s.get(Document, job.document_id)
        if doc and doc.status in ("queued", "processing"):
            doc.status = "canceled"
            doc.updated_at = _now_iso()
        s.commit()


def is_canceled(eng, job_id: str) -> bool:
    """Кооперативная точка отмены: воркер проверяет несколько раз за задачу."""
    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        job = s.get(Job, job_id)
        return bool(job and job.status == "canceled")


def wait_for_job(eng, job_id: str, timeout: float = 60.0, poll: float = 0.05) -> str:
    from app.db.session import SessionLocal

    deadline = datetime.now().timestamp() + timeout
    while datetime.now().timestamp() < deadline:
        with SessionLocal(eng) as s:
            job = s.get(Job, job_id)
            if job and job.status in ("done", "error", "canceled"):
                return job.status
        time.sleep(poll)
    return "timeout"


def mark_interrupted_from_previous_runs(eng) -> None:
    """При старте: running → interrupted; queued (старые) → canceled (§10.4)."""
    from app.db.session import SessionLocal
    from sqlalchemy import select

    with SessionLocal(eng) as s:
        for job in list(s.execute(select(Job).where(Job.status.in_(("running", "queued")))).scalars()):
            job.status = "interrupted" if job.status == "running" else "canceled"
            job.finished_at = _now_iso()
            doc = s.get(Document, job.document_id)
            if doc and doc.status == "processing":
                doc.status = "interrupted"
                doc.updated_at = _now_iso()
        s.commit()


import time


def _process(eng, job_id: str) -> None:
    """Жизненный цикл: queued → running → done|error|canceled;导入 — этап 1 корпус."""
    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        job = s.get(Job, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        job.started_at = _now_iso()
        job.pages_total = 1
        s.commit()
        doc = s.get(Document, job.document_id)
        doc.status = "processing"
        doc.updated_at = _now_iso()
        s.commit()

    try:
        if is_canceled(eng, job_id):
            return  # уже canceled — не трогаем статус
        _run_import(eng, job_id, doc.id)
    except CanceledPublic:
        return
    except Exception as exc:
        with SessionLocal(eng) as s:
            job = s.get(Job, job_id)
            if job.status == "canceled":
                return
            job.status = "error"
            job.error_message = str(exc)[:500]
            job.finished_at = _now_iso()
            d = s.get(Document, job.document_id)
            d.status = "error"
            d.error_message = str(exc)[:500]
            s.commit()
        return

    with SessionLocal(eng) as s:
        job = s.get(Job, job_id)
        if job.status == "canceled":
            return  # финализацию canceled уже сделал cancel()
        job.status = "done"
        job.progress = 100
        job.pages_done = job.pages_total = max(job.pages_total, 1)
        job.finished_at = _now_iso()
        d = s.get(Document, job.document_id)
        if d.status != "canceled":
            d.status = "ready"
        d.updated_at = _now_iso()
        s.commit()


def _run_import(eng, job_id: str, doc_id: str) -> None:
    """Импорт: pdf/image → страницы PNG; txt/docx/pdf_text → текст; сборка HTML.

    PDF обрабатывается постранично с кооперативной отменой (§10.4).
    """
    import asyncio
    import time
    from pathlib import Path

    from app.core.config import load_settings
    from app.db.models import Document, Page
    from app.db.session import SessionLocal as SL
    from app.pipeline.pages import extract_text_docx, extract_text_txt

    settings = load_settings()

    with SL(eng) as s:
        doc = s.get(Document, doc_id)
        total = doc.page_count or 1
        job = s.get(Job, job_id)
        job.pages_total = total
        s.commit()
    doc_dir = Path(settings.data_dir) / "documents" / doc_id
    original = next(iter(sorted(doc_dir.glob("original.*"))))
    ext = original.suffix.lower()

    t0 = time.perf_counter()
    paragraphs_by_page: list[list[str]] = []
    page_records: list[tuple[int, "object", int, int, int]] = []  # (page_no, image_path, w, h, has_text)

    if doc.source_type == "txt":
        paragraphs_by_page = [_plaintext_paragraphs(extract_text_txt(original))]
        page_records.append((1, "", 0, 0, 1))
    elif doc.source_type == "docx":
        paragraphs_by_page = [_plaintext_paragraphs(extract_text_docx(original))]
        page_records.append((1, "", 0, 0, 1))
    elif ext in (".png", ".jpg", ".jpeg"):
        from app.pipeline.pages import _render_image

        recs = _render_image(original, doc_dir / "pages", settings.ocr_dpi)
        for rec in recs:
            page_records.append((rec.page_no, rec.image_path, rec.width, rec.height, 0))
    else:  # pdf
        import pypdfium2 as pdfium

        try:
            pdf = pdfium.PdfDocument(str(original))
        except Exception as exc:
            raise PagesErrorPublic("Файл повреждён или защищён паролем") from exc
        pages_dir = doc_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        for i in range(len(pdf)):
            if is_canceled(eng, job_id):
                raise CanceledPublic()
            pil = pdf[i].render(scale=settings.ocr_dpi / 72).to_pil()
            out = pages_dir / f"{i + 1:04d}.png"
            pil.save(out)
            page_records.append((i + 1, f"pages/{i + 1:04d}.png", pil.width, pil.height, 0))
            from app.db.session import SessionLocal as SL2

            with SL2(eng) as s:
                j = s.get(Job, job_id)
                j.pages_done = i + 1
                j.progress = int(100 * (i + 1) / max(len(pdf), 1))
                s.commit()
        # текстовый слой PDF (могло быть определено в upload)
        if doc.source_type in ("pdf_text", "pdf_mixed"):
            text = _pdf_extract(original)
            paras = _plaintext_paragraphs(text)
            for i in range(0, len(paras), len(paras) // max(len(pdf), 1) + 1):
                chunks = paras[i:i + max(len(paras) // max(len(pdf), 1) + 1, 1)]
                if chunks:
                    paragraphs_by_page.append(chunks)

    html = _assemble_html(doc, paragraphs_by_page, len(page_records))
    from app.pipeline.sanitize import sanitize_html
    html = sanitize_html(html)

    with SL(eng) as s:
        for (page_no, image_path, w, h, has_text) in page_records:
            already = s.query(Page).filter_by(document_id=doc_id, page_no=page_no).first()
            if already:
                already.image_path = image_path
                already.width = w and w or already.width
                already.height = h or already.height
                already.has_text_layer = has_text
                already.status = "done"
            else:
                s.add(Page(
                    document_id=doc_id, page_no=page_no, image_path=image_path,
                    width=w, height=h, dpi=settings.ocr_dpi,
                    has_text_layer=has_text, ocr_used=0, status="done", blocks_json="[]",
                ))
        d = s.get(Document, doc_id)
        d.content_html = html
        d.content_version += 1
        d.processing_ms = int((time.perf_counter() - t0) * 1000)
        s.commit()


class PagesErrorPublic(RuntimeError):
    """Повреждённый/защищённый файл — сообщение пользователю."""


class CanceledPublic(RuntimeError):
    """Кооперативная отмена внутри _run_import."""


def _assemble_html(doc, paragraphs_by_page: list[list[str]], page_count: int) -> str:
    from app.pipeline.assemble import assemble_from_text

    if not paragraphs_by_page:
        paragraphs_by_page = [[
            "Страницы обработаны: изображения подготовлены. Распознавание текста — следующий шаг (кнопка «Обработать», этап 2)."
        ]]
    first = paragraphs_by_page[0][0] if paragraphs_by_page and paragraphs_by_page[0] else "Без названия"
    return assemble_from_text(
        first,
        pages_paragraphs=[(grp if grp else [""]) for grp in paragraphs_by_page],
        page_breaks_after=list(range(1, page_count + 1)) if page_count > 1 else None,
    )


def _plaintext_paragraphs(text: str) -> list[str]:
    out = []
    for para in text.split("\n\n"):
        para = " ".join(line.strip() for line in para.splitlines()).strip()
        if para:
            out.append(para)
    return out


def _pdf_extract(path) -> str:
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            pages = []
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
            return "\n\n".join(t for t in pages if t.strip())
    except Exception:
        return ""
