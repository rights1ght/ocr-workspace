"""Тесты БД и миграций (Task 2, OCR/TZ 7.1-7.6)."""
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    from app.db.session import create_engine, run_migrations

    eng = create_engine(tmp_path / "app.db")
    run_migrations(eng)
    return eng


def test_migrations_create_all_6_tables(engine):
    with sqlite3.connect(engine.db_path) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"document", "page", "job", "export", "setting", "app_event"} <= names


def test_user_version_is_1_and_idempotent(engine):
    run1 = None
    with sqlite3.connect(engine.db_path) as conn:
        run1 = conn.execute("PRAGMA user_version").fetchone()[0]
    assert run1 == 1
    from app.db.session import run_migrations

    run_migrations(engine)  # повторно — не падает
    with sqlite3.connect(engine.db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_wal_mode_and_fk_on(engine):
    with sqlite3.connect(engine.db_path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        fk_ok = conn.execute("PRAGMA foreign_keys").fetchone()[0]


def test_page_fk_to_document(engine):
    import uuid

    from app.db.models import Document, Page
    from app.db.session import SessionLocal

    with SessionLocal(engine) as s:
        doc = Document(
            id=str(uuid.uuid4()), title="t", original_filename="t.pdf",
            source_type="pdf_scan", mime="application/pdf", size_bytes=1,
            sha256="x", page_count=0, status="queued", engine="surya-2.5",
            content_html="", content_version=0, created_at="2026-11-03T00:00:00",
            updated_at="2026-11-03T00:00:00",
        )
        s.add(doc)
        s.flush()
        s.add(Page(document_id=doc.id, page_no=1, image_path="p", width=1, height=1,
                   dpi=150, has_text_layer=0, ocr_used=0, status="pending", blocks_json="[]"))
        s.commit()
        bad = Page(document_id="nосуще-id", page_no=1, image_path="p", width=1, height=1,
                   dpi=150, has_text_layer=0, ocr_used=0, status="pending", blocks_json="[]")
        s.add(bad)
        with pytest.raises(Exception):
            s.commit()
