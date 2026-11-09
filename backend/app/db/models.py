"""ORM-модели (OCR/TZ 7.2). Имена полей — точно как в ТЗ."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import Integer, Text as SAText
from sqlalchemy import Column


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "document"
    id = Column(SAText, primary_key=True)
    title = Column(SAText, nullable=False)
    original_filename = Column(SAText, nullable=False)
    source_type = Column(SAText, nullable=False)
    mime = Column(SAText, nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    sha256 = Column(SAText, nullable=False, default="")
    page_count = Column(Integer, nullable=False, default=0)
    status = Column(SAText, nullable=False, default="queued")
    engine = Column(SAText, nullable=False, default="")
    content_html = Column(SAText, nullable=False, default="")
    content_version = Column(Integer, nullable=False, default=0)
    low_confidence = Column(Integer, nullable=False, default=0)
    error_message = Column(SAText)
    processing_ms = Column(Integer)
    created_at = Column(SAText, nullable=False)
    updated_at = Column(SAText, nullable=False)


class Page(Base):
    __tablename__ = "page"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(SAText, nullable=False)
    page_no = Column(Integer, nullable=False)
    image_path = Column(SAText, nullable=False, default="")
    width = Column(Integer, nullable=False, default=0)
    height = Column(Integer, nullable=False, default=0)
    dpi = Column(Integer, nullable=False, default=0)
    has_text_layer = Column(Integer, nullable=False, default=0)
    ocr_used = Column(Integer, nullable=False, default=0)
    status = Column(SAText, nullable=False, default="pending")
    error_message = Column(SAText)
    blocks_json = Column(SAText, nullable=False, default="[]")


class Job(Base):
    __tablename__ = "job"
    id = Column(SAText, primary_key=True)
    document_id = Column(SAText, nullable=False)
    type = Column(SAText, nullable=False)
    status = Column(SAText, nullable=False, default="queued")
    progress = Column(Integer, nullable=False, default=0)
    pages_done = Column(Integer, nullable=False, default=0)
    pages_total = Column(Integer, nullable=False, default=0)
    eta_seconds = Column(Integer)
    started_at = Column(SAText)
    finished_at = Column(SAText)
    error_message = Column(SAText)


class Export(Base):
    __tablename__ = "export"
    id = Column(SAText, primary_key=True)
    document_id = Column(SAText, nullable=False)
    format = Column(SAText, nullable=False)
    file_path = Column(SAText, nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    options_json = Column(SAText, nullable=False, default="{}")
    created_at = Column(SAText, nullable=False)


class Setting(Base):
    __tablename__ = "setting"
    key = Column(SAText, primary_key=True)
    value = Column(SAText, nullable=False, default="{}")


class AppEvent(Base):
    __tablename__ = "app_event"
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(SAText, nullable=False)
    message = Column(SAText, nullable=False)
    context_json = Column(SAText, nullable=False, default="{}")
    created_at = Column(SAText, nullable=False)
