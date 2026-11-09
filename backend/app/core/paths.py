"""Каталоги данных (OCR/TZ 7.1)."""
from __future__ import annotations

from pathlib import Path


def ensure_dirs(data_dir: Path) -> None:
    for sub in ("documents", "exports", "logs", "tmp", "backups"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)


def get_data_dir(data_dir: Path) -> Path:
    ensure_dirs(data_dir)
    return data_dir
