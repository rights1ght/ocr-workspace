"""Тесты очереди задач и воркера (Task 6, OCR/TZ §10.4)."""
import time
import uuid

import pytest


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    from app.db.session import create_engine, run_migrations
    from pathlib import Path

    eng = create_engine(Path(tmp_path) / "app.db")
    run_migrations(eng)
    return eng


def _make_document(env, source_type: str = "txt") -> str:
    from app.db.models import Document
    from app.db.session import SessionLocal

    doc_id = str(uuid.uuid4())
    with SessionLocal(env) as s:
        s.add(Document(
            id=doc_id, title="t", original_filename="notes.txt",
            source_type=source_type, mime="text/plain", size_bytes=10,
            sha256=doc_id, page_count=0, status="queued", engine="plain",
            content_html="", content_version=0,
            created_at="2026-11-03T00:00:00", updated_at="2026-11-03T00:00:00",
        ))
        s.commit()
    return doc_id


def _doc_dir(tmp_path, doc_id: str):
    from app.core.config import load_settings

    d = load_settings().data_dir / "documents" / doc_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "original.txt").write_text("Копейки.\n", encoding="utf-8")
    return d


def test_job_lifecycle_queued_running_done(env, tmp_path):
    from app.db.models import Job
    from app.db.session import SessionLocal
    from app.jobs.queue import enqueue, wait_for_job

    doc_id = _make_document(env)
    _doc_dir(tmp_path, doc_id)
    job_id = enqueue(env, doc_id)
    status = wait_for_job(env, job_id, timeout=10)
    assert status == "done"
    with SessionLocal(env) as s:
        job = s.get(Job, job_id)
        assert job.progress == 100
        assert job.finished_at is not None
    from app.db.models import Document

    with SessionLocal(env) as s:
        doc = s.get(Document, doc_id)
        assert doc.status == "ready"
        assert "data-src-page" in doc.content_html


def test_cancel_mid_processing(env, tmp_path, monkeypatch):
    from app.db.models import Job
    from app.db.session import SessionLocal
    from app.jobs import queue
    from app.jobs.queue import cancel, enqueue, wait_for_job

    def slow_import(eng, job_id, doc_id):
        time.sleep(0.8)

    monkeypatch.setattr(queue, "_run_import", slow_import)
    doc_id = _make_document(env)
    _doc_dir(tmp_path, doc_id)
    job_id = enqueue(env, doc_id)
    time.sleep(0.1)  # дать воркеру стать running
    cancel(env, job_id)
    status = wait_for_job(env, job_id, timeout=10)
    assert status == "canceled"


def test_processing_jobs_marked_interrupted_on_startup(env, tmp_path):
    from app.db.models import Job
    from app.db.session import SessionLocal
    from app.jobs.queue import mark_interrupted_from_previous_runs, enqueue

    doc_id = _make_document(env)
    with SessionLocal(env) as s:
        s.add(Job(id="j1", document_id=doc_id, type="process", status="running",
                  progress=50, pages_done=1, pages_total=2))
        s.add(Job(id="j2", document_id=doc_id, type="process", status="queued"))
        s.commit()
    mark_interrupted_from_previous_runs(env)
    with SessionLocal(env) as s:
        assert s.get(Job, "j1").status == "interrupted"
        assert s.get(Job, "j2").status == "canceled"
