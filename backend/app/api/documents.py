"""API документов: загрузка, список, карточка, удаление (OCR/TZ §6.2, US-1, SEC-2/3)."""
from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Document
from app.pipeline.detect import (
    MAGIC,
    _is_docx,
    pdf_page_count,
    pdf_text_density,
)

router = APIRouter(prefix="/api/documents")

EXT_FOR = {"png": "png", "jpeg": "jpg", "pdf": "pdf", "docx_or_zip": "docx", "txt": "txt"}
MIME_FOR = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "pdf": "application/pdf",
    "docx_or_zip": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _session(eng):
    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        yield s


def _sniff_kind(data: bytes) -> str | None:
    head = data[:16]
    if head.startswith(MAGIC["png"]):
        return "png"
    if head.startswith(MAGIC["jpeg"]):
        return "jpeg"
    if head.startswith(MAGIC["pdf"]):
        return "pdf"
    if head.startswith(MAGIC["docx"]):
        return "docx_or_zip"
    try:
        text = data.decode("utf-8")
        if not text or text.isprintable() or "\n" in text:
            return "txt"
    except UnicodeDecodeError:
        pass
    return None


def _classify(original: Path, kind: str) -> str:
    """source_type по ТЗ §7.2."""
    if kind in ("png", "jpeg"):
        return "image"
    if kind == "txt":
        return "txt"
    if kind == "docx_or_zip":
        return "docx" if _is_docx(original) else "zip"
    try:
        with_len, total = pdf_text_density(original)
    except Exception:
        return "pdf_scan"
    if with_len == total:
        return "pdf_text"
    if with_len == 0:
        return "pdf_scan"
    return "pdf_mixed"


def _count_pages(original: Path, kind: str) -> int:
    if kind == "pdf":
        try:
            return pdf_page_count(original)
        except Exception:
            return 0
    return 1


@router.post("", status_code=201)
def upload_document(request: Request, file: UploadFile = File(...)) -> dict:
    settings: Settings = request.app.state.settings
    eng = request.app.state.engine
    raw_name = Path(file.filename or "").name or "безымянный"

    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"Файл больше {settings.max_upload_mb} МБ")

    kind = _sniff_kind(data)
    if kind not in EXT_FOR:
        raise HTTPException(
            415, "Неподдерживаемый файл: формат определяется по содержимому (PDF/JPG/PNG/DOCX/TXT)"
        )

    sha256 = hashlib.sha256(data).hexdigest()
    doc_id = str(uuid.uuid4())
    doc_dir = settings.data_dir / "documents" / doc_id
    doc_dir.mkdir(parents=True, exist_ok=False)

    ext = EXT_FOR[kind]
    original = doc_dir / f"original.{ext}"
    original.write_bytes(data)

    source_type = _classify(original, kind)
    if source_type == "zip":
        shutil.rmtree(doc_dir, ignore_errors=True)
        raise HTTPException(415, "Неподдерживаемый файл (ZIP без DOCX-содержимого)")

    page_count = _count_pages(original, kind)
    if page_count > settings.max_pages:
        shutil.rmtree(doc_dir, ignore_errors=True)
        raise HTTPException(409, f"Слишком много страниц: {page_count} > лимита {settings.max_pages}")

    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        duplicate = s.execute(select(Document.id).where(Document.sha256 == sha256)).first() is not None
        doc = Document(
            id=doc_id, title=Path(raw_name).stem, original_filename=raw_name,
            source_type=source_type, mime=MIME_FOR[kind] if kind in MIME_FOR else "application/octet-stream",
            size_bytes=len(data), sha256=sha256, page_count=page_count,
            status="queued", engine={"pdf_text": "pdf-text", "pdf_scan": "surya-2.5",
                                     "pdf_mixed": "surya-2.5", "docx": "docx", "txt": "plain",
                                     "image": "surya-2.5"}[source_type],
            created_at=_now_iso(), updated_at=_now_iso(),
        )
        s.add(doc)
        s.commit()

    from app.jobs.queue import enqueue

    job_id = enqueue(eng, doc_id)

    return {
        "id": doc_id, "title": doc.title, "original_filename": raw_name,
        "source_type": source_type, "status": doc.status, "page_count": page_count,
        "duplicate": duplicate, "dir": str(doc_dir), "job_id": job_id,
    }


@router.post("/{doc_id}/process", status_code=202)
def reprocess_document(doc_id: str, request: Request) -> dict:
    eng = request.app.state.engine
    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        if s.get(Document, doc_id) is None:
            raise HTTPException(404, "Документ не найден")
    from app.jobs.queue import enqueue

    return {"job_id": enqueue(eng, doc_id)}


@router.get("/{doc_id}/pages")
def list_pages(doc_id: str, request: Request) -> list[dict]:
    eng = request.app.state.engine
    from sqlalchemy import select
    from app.db.models import Page
    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        if s.get(Document, doc_id) is None:
            raise HTTPException(404, "Документ не найден")
        rows = list(s.execute(select(Page).where(Page.document_id == doc_id).order_by(Page.page_no)).scalars())
        return [dict(
            page_no=p.page_no, image_path=p.image_path, width=p.width, height=p.height,
            dpi=p.dpi, has_text_layer=p.has_text_layer, ocr_used=p.ocr_used,
            status=p.status, blocks_json=p.blocks_json,
        ) for p in rows]


@router.get("/{doc_id}/pages/{page_no}.png")
def get_page_png(doc_id: str, page_no: int, request: Request):
    """PNG-страница документа; путь собирается только из doc_id (UUID) и page_no (int) — SEC-2."""
    from fastapi.responses import FileResponse

    from app.db.session import SessionLocal

    settings: Settings = request.app.state.settings
    eng = request.app.state.engine
    with SessionLocal(eng) as s:
        if s.get(Document, doc_id) is None:
            raise HTTPException(404, "Документ не найден")
    path = settings.data_dir / "documents" / doc_id / "pages" / f"{page_no:04d}.png"
    if not path.is_file():
        raise HTTPException(404, "Страница ещё не отрендерена")
    return FileResponse(path, media_type="image/png")


@router.get("")
def list_documents(request: Request, q: str = "", status: str = "") -> list[dict]:
    eng = request.app.state.engine
    stmt = select(Document).order_by(Document.created_at.desc())
    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        docs = list(s.execute(stmt).scalars())
        out = [_doc_brief(d) for d in docs]
    if q:
        out = [d for d in out if q.lower() in d["title"].lower()]
    if status:
        out = [d for d in out if d["status"] == status]
    return out


@router.get("/{doc_id}")
def get_document(doc_id: str, request: Request) -> dict:
    eng = request.app.state.engine
    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        doc = s.get(Document, doc_id)
        if doc is None:
            raise HTTPException(404, "Документ не найден")
        return _doc_full(doc)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, request: Request) -> None:
    settings: Settings = request.app.state.settings
    eng = request.app.state.engine
    from app.db.session import SessionLocal

    with SessionLocal(eng) as s:
        doc = s.get(Document, doc_id)
        if doc is None:
            raise HTTPException(404, "Документ не найден")
        s.delete(doc)
        s.commit()
    shutil.rmtree(settings.data_dir / "documents" / doc_id, ignore_errors=True)


def _doc_brief(d: Document) -> dict:
    return {
        "id": d.id, "title": d.title, "status": d.status, "source_type": d.source_type,
        "page_count": d.page_count, "size_bytes": d.size_bytes,
        "created_at": d.created_at, "updated_at": d.updated_at,
    }


def _doc_full(d: Document) -> dict:
    out = _doc_brief(d)
    out.update(
        original_filename=d.original_filename, mime=d.mime, sha256=d.sha256,
        engine=d.engine, content_html=d.content_html, content_version=d.content_version,
        low_confidence=d.low_confidence, error_message=d.error_message,
        processing_ms=d.processing_ms,
    )
    return out
