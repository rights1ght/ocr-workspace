"""Рендер страниц PDF/изображений и извлечение текста DOCX/TXT (Task 4, ТЗ §7.1/§8.2)."""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PageRecord:
    page_no: int
    image_path: str
    width: int
    height: int
    dpi: int
    has_text_layer: int


class PagesError(RuntimeError):
    """Авария рендера: повреждённый/защищённый файл и т. п."""


def render_pages(doc_path: Path, doc_dir: Path, dpi: int = 150) -> list[PageRecord]:
    """Готовит data/pages/000N.png и возвращает записи страниц.

    pdf → pypdfium2 render; image → exif_transpose + пересохранение PNG.
    DOCX/TXT страниц не создают (extract_text_*).
    """
    ext = doc_path.suffix.lower()
    pages_dir = doc_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    kind = "pdf" if ext == ".pdf" else "image"
    if kind == "pdf":
        return _render_pdf(doc_path, pages_dir, dpi)
    return _render_image(doc_path, pages_dir, dpi)


def _render_pdf(doc_path: Path, pages_dir: Path, dpi: int) -> list[PageRecord]:
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(doc_path))
    except Exception as exc:  # повреждён или защищён
        raise PagesError("Файл повреждён или защищён паролем") from exc
    recs: list[PageRecord] = []
    try:
        for i in range(len(pdf)):
            bitmap = pdf[i]
            pil = bitmap.render(scale=dpi / 72).to_pil()
            out = pages_dir / f"{i + 1:04d}.png"
            pil.save(out)
            recs.append(
                PageRecord(
                    page_no=i + 1, image_path=str(out.relative_to(doc_path.parent)),
                    width=pil.width, height=pil.height, dpi=dpi,
                    has_text_layer=1 if _page_text_reportlab(doc_path, i) else 0,
                )
            )
    except PagesError:
        raise
    except Exception as exc:
        raise PagesError(f"Не удалось отрендерить PDF: {exc}") from exc
    return recs


def _page_text_reportlab(_doc_path: Path, _i: int) -> bool:
    return False  # определение текстового слоя для pdf делается в detect (pdfplumber)


def _render_image(doc_path: Path, pages_dir: Path, dpi: int) -> list[PageRecord]:
    from PIL import Image, ImageOps

    pages_dir.mkdir(parents=True, exist_ok=True)

    try:
        img = Image.open(doc_path)
    except Exception as exc:
        raise PagesError("Не удалось открыть изображение") from exc
    img = ImageOps.exif_transpose(img).convert("RGB")
    out = pages_dir / "0001.png"
    img.save(out)
    return [
        PageRecord(
            page_no=1, image_path="pages/0001.png",
            width=img.width, height=img.height, dpi=dpi, has_text_layer=0,
        )
    ]


def extract_text_docx(path: Path) -> str:
    try:
        import docx as docxlib

        d = docxlib.Document(str(path))
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                parts.append(" | ".join(cells))
        return "\n".join(parts)
    except Exception as exc:
        raise PagesError("Повреждённый DOCX") from exc


def extract_text_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def page_has_text_stream(pdf_bytes: bytes) -> bool:
    """Есть ли текстовый слой у одностраничного PDF-байтов (для теста)."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return any(len((p.extract_text() or "")) > 0 for p in pdf.pages)
