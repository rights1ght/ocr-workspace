"""Тесты рендера страниц (Task 4, OCR/TZ §7.1 pages/, US-2/3/4)."""
import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


def _pdf_bytes(pages: int = 3) -> bytes:
    imgs = [Image.new("RGB", (300, 300), "white") for _ in range(pages)]
    buf = io.BytesIO()
    img0 = imgs[0]
    img0.save(buf, "PDF", save_all=True, append_images=imgs[1:])
    return buf.getvalue()


def _docx_bytes() -> bytes:
    import docx as docxlib

    buf = io.BytesIO()
    d = docxlib.Document()
    d.add_paragraph("Абзац один с длинным текстом для проверки.")
    d.add_paragraph("Абзац два.")
    d.save(buf)
    return buf.getvalue()


def test_render_pdf_pages(tmp_path):
    from app.pipeline.pages import render_pages

    src = tmp_path / "original.pdf"
    src.write_bytes(_pdf_bytes(3))
    recs = render_pages(src, tmp_path, dpi=150)
    assert len(recs) == 3
    p1 = tmp_path / "pages" / "0001.png"
    assert p1.is_file()
    assert recs[0].width == recs[0].height != 0
    assert recs[1].image_path.endswith("0002.png")


def test_render_image_png(tmp_path):
    from app.pipeline.pages import render_pages

    buf = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(buf, "PNG")
    (tmp_path / "original.png").write_bytes(buf.getvalue())
    recs = render_pages(tmp_path / "original.png", tmp_path, dpi=150)
    assert len(recs) == 1
    assert (tmp_path / "pages" / "0001.png").is_file()


def test_render_jpg_with_exif_transpose(tmp_path):
    from app.pipeline.pages import render_pages

    buf = io.BytesIO()
    img = Image.new("RGB", (80, 60), "white")
    ex = img.getexif()
    ex[0x112] = 6
    img.save(buf, "JPEG", exif=ex.tobytes())
    (tmp_path / "original.jpg").write_bytes(buf.getvalue())
    recs = render_pages(tmp_path / "original.jpg", tmp_path, dpi=150)
    assert len(recs) == 1
    from PIL import ImageOps

    out = Image.open(tmp_path / "pages" / "0001.png")
    # после transpose размеры станут (60, 80)>? orientation 6 → width/height меняются местами
    assert recs[0].width == 60 and recs[0].height == 80


def test_render_docx_and_txt_no_pages_images_but_text(tmp_path):
    from app.pipeline.pages import extract_text_docx, extract_text_txt

    (tmp_path / "original.docx").write_bytes(_docx_bytes())
    text = extract_text_docx(tmp_path / "original.docx")
    assert "Абзац один" in text
    (tmp_path / "original.txt").write_text("Текст строки.\nВторая.\n", encoding="utf-8")
    assert "Вторая" in extract_text_txt(tmp_path / "original.txt")


def test_corrupt_pdf_raises_clear_error(tmp_path):
    from app.pipeline.pages import PagesError, render_pages

    (tmp_path / "original.pdf").write_bytes(b"%PDF-1.4 \xc7\xa5 garbage not a real pdf")
    with pytest.raises(PagesError) as e:
        render_pages(tmp_path / "original.pdf", tmp_path, dpi=150)
    assert "повреждён или защищён" in str(e.value)


def test_pdf_text_layer_detection_digital_pdf(tmp_path):
    """Цифровой PDF (reportlab, настоящий текстовый слой) has_text_layer=True."""
    import reportlab.lib.pagesizes as ps
    from reportlab.pdfgen import canvas

    from app.pipeline.pages import page_has_text_stream

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=ps.A4)
    draw = c.beginText(40, 760)
    draw.setFont("Helvetica", 12)
    draw.textLine("Hello World Text Scan Test")
    c.drawText(draw)
    c.showPage()
    c.save()
    assert page_has_text_stream(buf.getvalue()) is True
