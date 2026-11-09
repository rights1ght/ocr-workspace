"""Детекция типа источника (OCR/TZ §7.2 source_type, SEC-3 magic bytes)."""
from __future__ import annotations

from pathlib import Path

MAGIC = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
    "pdf": b"%PDF-",
    "docx": b"PK\x03\x04",
}


def sniff_kind(path: Path) -> str | None:
    head = path.open("rb").read(16)
    if head.startswith(MAGIC["png"]):
        return "png"
    if head.startswith(MAGIC["jpeg"]):
        return "jpeg"
    if head.startswith(MAGIC["pdf"]):
        return "pdf"
    if head.startswith(MAGIC["docx"]) and _is_docx(path):
        return "docx"
    if head.startswith(MAGIC["docx"]):
        return "zip"  # zip не docx — отклонить
    try:
        text = path.read_text(encoding="utf-8")
        if text.isprintable() or "\n" in text or text == "":
            return "txt"
    except UnicodeDecodeError:
        pass
    return None


def _is_docx(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            return any(n.startswith("word/") for n in z.namelist())
    except Exception:
        return False


def pdf_page_count(path: Path) -> int:
    import pypdfium2 as pdfium

    return len(pdfium.PdfDocument(str(path)))


def pdf_text_density(path: Path) -> tuple[int, int]:
    """(страниц с текстом >50 символов, всего страниц)."""
    import pdfplumber

    with pdfplumber.open(str(path)) as pdf:
        total = len(pdf.pages)
        with_len = sum(1 for p in pdf.pages if len((p.extract_text() or "")) > 50)
    return with_len, total


def detect_source(path: Path) -> str:
    kind = sniff_kind(path)
    if kind == "png":
        return "image"
    if kind == "jpeg":
        return "image"
    if kind == "txt":
        return "txt"
    if kind == "docx":
        return "docx"
    if kind == "pdf":
        try:
            with_len, total = pdf_text_density(path)
        except Exception:
            return "pdf_scan"
        if with_len == total:
            return "pdf_text"
        if with_len == 0:
            return "pdf_scan"
        return "pdf_mixed"
    raise ValueError(f"Неизвестный формат: {kind}")


import zipfile  # noqa: E402
