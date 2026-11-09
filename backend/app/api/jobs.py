"""API задач: карточка job, SSE-поток состояния (OCR/TZ §6.4 §10.8 progress)."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.db.models import Job
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/jobs")


def _job_out(j: Job) -> dict:
    return {
        "id": j.id, "document_id": j.document_id, "type": j.type, "status": j.status,
        "progress": j.progress, "pages_done": j.pages_done, "pages_total": j.pages_total,
        "eta_seconds": j.eta_seconds, "error_message": j.error_message,
    }


@router.get("/{job_id}")
def get_job(job_id: str, request: Request) -> dict:
    eng = request.app.state.engine
    with SessionLocal(eng) as s:
        job = s.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Задача не найдена")
        return _job_out(job)


@router.get("/{job_id}/events")
def job_events(job_id: str, request: Request) -> StreamingResponse:
    eng = request.app.state.engine

    async def gen():
        last = None
        while True:
            with SessionLocal(eng) as s:
                job = s.get(Job, job_id)
                state = _job_out(job) if job else {"status": "error", "error_message": "не найдена"}
            wire = json.dumps(state, ensure_ascii=False)
            if wire != last:
                last = wire
                yield f"data: {wire}\n\n"
            if state["status"] in ("done", "error", "canceled"):
                yield "event: end\ndata: {}\n\n"
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(gen(), media_type="text/event-stream")
