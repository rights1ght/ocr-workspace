"""Тесты: автозапуск job при загрузке, SSE-поток прогресса, pages-рендер в job (Task 7)."""
import io
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    from app.main import create_app

    return TestClient(create_app())


def _txt_bytes() -> bytes:
    return "Мой Heading\n\nПервый абзац заметки.\n\nВторой абзац.\n".encode("utf-8")


def test_upload_enqueues_job_and_becomes_ready(client, tmp_path):
    r = client.post("/api/documents", files={"file": ("заметка.txt", _txt_bytes(), "text/plain")})
    doc = r.json()
    assert r.status_code == 201
    assert doc["job_id"]
    deadline = time.time() + 10
    while time.time() < deadline:
        d = client.get(f"/api/documents/{doc['id']}").json()
        if d["status"] in ("ready", "error"):
            break
        time.sleep(0.1)
    assert d["status"] == "ready"
    assert "Мой Heading" in d["content_html"]
    assert "Первый абзац" in d["content_html"]


def test_document_card_has_pages(tmp_path, client):
    buf = io.BytesIO()
    imgs = [Image.new("RGB", (300, 300), "white"), Image.new("RGB", (300, 300), "white")]
    imgs[0].save(buf, "PDF", save_all=True, append_images=imgs[1:])
    head = buf.tell()
    r = client.post("/api/documents", files={"file": ("два.pdf", buf.getvalue(), "application/pdf")})
    assert r.status_code == 201, r.text
    doc = r.json()
    deadline = time.time() + 15
    while time.time() < deadline:
        d = client.get(f"/api/documents/{doc['id']}").json()
        if d["status"] in ("ready", "error"):
            break
        time.sleep(0.2)
    assert d["status"] == "ready", d.get("error_message")
    pages = client.get(f"/api/documents/{doc['id']}/pages").json()
    assert len(pages) == 2
    assert pages[0]["image_path"].endswith("0001.png")
    assert (tmp_path / "documents" / doc["id"] / "pages" / "0001.png").is_file()


def test_sse_job_events(client, tmp_path):
    r = client.post("/api/documents", files={"file": ("ссе.txt", _txt_bytes(), "text/plain")})
    doc = r.json()
    with client.stream("GET", f"/api/jobs/{doc['job_id']}/events") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = []
        for line in resp.iter_lines():
            if line.startswith("data:"):
                payload = json.loads(line[5:])
                if "status" in payload:
                    events.append(payload)
            if len(events) >= 3:
                break
    assert events[-1]["status"] in ("running", "done")


def test_process_endpoint_reenqueue(client, tmp_path):
    r = client.post("/api/documents", files={"file": ("повт.txt", _txt_bytes(), "text/plain")})
    doc = r.json()
    assert client.post(f"/api/documents/{doc['id']}/process").status_code == 202


def test_page_png_served(tmp_path, client):
    buf = io.BytesIO()
    Image.new("RGB", (120, 90), "white").save(buf, "PNG")
    r = client.post("/api/documents", files={"file": ("фото.png", buf.getvalue(), "image/png")})
    doc = r.json()
    deadline = time.time() + 10
    while time.time() < deadline:
        d = client.get(f"/api/documents/{doc['id']}").json()
        if d["status"] in ("ready", "error"):
            break
        time.sleep(0.1)
    assert d["status"] == "ready", d.get("error_message")
    r2 = client.get(f"/api/documents/{doc['id']}/pages/1.png")
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "image/png"
    assert r2.content[:8] == b"\x89PNG\r\n\x1a\n"
    #Traversal: чужой путь невозможен по построению (doc_id UUID, page_no int)
    r3 = client.get(f"/api/documents/{doc['id']}/pages/2.png")
    assert r3.status_code == 404
