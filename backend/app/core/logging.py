"""Логирование (OCR/TZ 10.7): data/logs/app.log, ротация 10 МБ, 3 файла."""
from __future__ import annotations

import logging
import logging.handlers
import sys

FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(data_dir, debug: bool) -> None:
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = logging.handlers.RotatingFileHandler(
        data_dir / "logs" / "app.log", maxBytes=10_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(FMT))
    root.addHandler(fh)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter(FMT))
    root.addHandler(sh)
