"""Тесты каркаса приложения (Task 1: config/paths/logging/health)."""
from pathlib import Path

from fastapi.testclient import TestClient


def test_health_ok_and_dirs_created(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    from app.main import create_app

    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    d = Path(tmp_path)
    assert (d / "documents").is_dir()
    assert (d / "logs").is_dir()
    assert (d / "tmp").is_dir()


def test_config_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_PORT", "9999")
    monkeypatch.setenv("MAX_UPLOAD_MB", "50")
    from app.core.config import load_settings

    s = load_settings()
    assert s.port == 9999
    assert s.max_upload_mb == 50
    assert s.max_pages == 200
    assert s.ocr_dpi == 150
    assert s.data_dir == Path(tmp_path)
