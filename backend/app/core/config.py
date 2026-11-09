"""Конфигурация приложения (OCR/TZ 10.8)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    port: int
    debug: bool
    max_upload_mb: int
    max_pages: int
    ocr_dpi: int
    llama_port: int

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


def load_settings() -> Settings:
    return Settings(
        data_dir=Path(os.environ.get("APP_DATA_DIR", DEFAULT_DATA_DIR)),
        port=int(os.environ.get("APP_PORT", "8765")),
        debug=os.environ.get("APP_DEBUG") == "1",
        max_upload_mb=int(os.environ.get("MAX_UPLOAD_MB", "200")),
        max_pages=int(os.environ.get("MAX_PAGES", "200")),
        ocr_dpi=int(os.environ.get("OCR_DPI", "150")),
        llama_port=int(os.environ.get("LLAMA_PORT", "8181")),
    )
