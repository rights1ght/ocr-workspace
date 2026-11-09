"""Тесты загрузки и детекции типа источника (Task 3, OCR/TZ §7.2 SEC-3)."""
import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    from app.main import create_app

    return TestClient(create_app())


def _png_bytes() -> bytes:
    img = Image.new("RGB", (60, 40), "white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _pdf_bytes(pages: int = 1) -> bytes:
    img = Image.new("RGB", (300, 300), "white")
    buf = io.BytesIO()
    img.save(buf, "PDF", save_all=True, append_images=[Image.new("RGB", (300, 300), "white")] * (pages - 1))
    return buf.getvalue()


def _docx_bytes() -> bytes:
    import docx as docxlib

    buf = io.BytesIO()
    d = docxlib.Document()
    d.add_paragraph("Привет, тестовый документ.")
    d.save(buf)
    return buf.getvalue()


def _upload(client, data: bytes, name: str, mime: str = "application/octet-stream"):
    return client.post("/api/documents", files={"file": (name, data, mime)})


def test_upload_png_image_creates_document(client, tmp_path):
    r = _upload(client, _png_bytes(), "фото.png", "image/png")
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["title"] == "фото"
    assert doc["source_type"] == "image"
    assert doc["status"] == "queued"
    assert Path(doc["dir"], "original.png").exists()


def test_upload_pdf_scan(client):
    r = _upload(client, _pdf_bytes(1), "scan.pdf", "application/pdf")
    assert r.status_code == 201, r.text
    assert r.json()["source_type"] == "pdf_scan"


def test_upload_docx(client):
    r = _upload(client, _docx_bytes(), "док.docx")
    assert r.status_code == 201, r.text
    assert r.json()["source_type"] == "docx"


def test_upload_txt(client):
    r = _upload(client, "строка один.\nстрока два.\n".encode(), "заметка.txt")
    assert r.status_code == 201, r.text
    assert r.json()["source_type"] == "txt"


def test_upload_forged_extension_rejected(client):
    r = _upload(client, b"MZ\x90\x00" + b"\x00" * 512, "стемы.pdf", "application/pdf")
    assert r.status_code == 415
    assert "Неподдерживаемый" in r.json()["detail"]


def test_upload_duplicate(client):
    data = _png_bytes()
    r1 = _upload(client, data, "a.png", "image/png")
    r2 = _upload(client, data, "b.png", "image/png")
    assert r1.json()["id"] != r2.json()["id"]
    assert r2.json()["duplicate"] is True
    assert r1.json()["duplicate"] is False


def test_upload_traversal_name_is_safe(client, tmp_path):
    r = _upload(client, _png_bytes(), "../../evil.png", "image/png")
    assert r.status_code == 201
    assert "/" not in r.json()["original_filename"] and ".." not in r.json()["original_filename"]
    doc_dir = Path(tmp_path) / "documents"
    created = list(doc_dir.iterdir())
    assert all(d.is_dir() for d in created)  # только UUID-каталоги


def test_upload_pdf_too_many_pages(client):
    r = _upload(client, _pdf_bytes(205), "большой.pdf", "application/pdf")
    assert r.status_code == 409
    assert "страниц" in r.json()["detail"]


def test_detect_png_docx_txt_helpers(client, tmp_path):
    from app.pipeline.detect import detect_source, sniff_kind

    p = tmp_path / "x.png"
    p.write_bytes(_png_bytes())
    assert sniff_kind(p) == "png"
    assert detect_source(p) == "image"
    p2 = tmp_path / "y.docx"
    p2.write_bytes(_docx_bytes())
    assert detect_source(p2) == "docx"
    p3 = tmp_path / "z.txt"
    p3.write_text("текст\n", encoding="utf-8")
    assert detect_source(p3) == "txt"
