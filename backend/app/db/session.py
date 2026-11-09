"""SQLAlchemy Core-движок + последовательные SQL-миграции (OCR/TZ 7.6)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine as _sa_create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class Engine:
    """Обёртка над sqlalchemy engine с путём к файлу БД."""

    db_path: Path

    def __init__(self, sa_engine, db_path: Path):
        self._sa = sa_engine
        self.db_path = db_path

    def connect(self):
        return self._sa.connect()


def create_engine(db_path: Path) -> Engine:
    sa = _sa_create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(sa, "connect")
    def _on_connect(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    eng = Engine(sa, db_path)
    eng.SessionLocal = sessionmaker(bind=sa, expire_on_commit=False)
    return eng


class SessionLocal:
    """Контекстный менеджер: with SessionLocal(eng) as s: ..."""

    def __init__(self, eng: Engine):
        self._s = eng.SessionLocal()

    def __enter__(self):
        return self._s

    def __exit__(self, *exc):
        self._s.close()


def run_migrations(eng: Engine) -> None:
    db_path = eng.db_path
    applied = user_version(db_path)
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for path in files:
        version = int(path.name.split("-", 1)[0])
        if version > applied:
            _apply(db_path, path, version)


def user_version(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _apply(db_path: Path, path: Path, version: int) -> None:
    sql = path.read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(sql)
        conn.execute(f"PRAGMA user_version = {version}")
