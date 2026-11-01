"""Recruiter report details and the AI summary (recruiter key). Work is in backend/report."""

import uuid
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.recruiter import require_recruiter
from app.routes.sessions import DbSession
from report import build as report_build
from report import summary as report_summary

router = APIRouter(prefix="/sessions", tags=["report"], dependencies=[Depends(require_recruiter)])


class SummaryOut(BaseModel):
    summary: str
    label: str


def _details(db: DbSession, session_id: uuid.UUID) -> report_build.ReportDetails:
    try:
        details = report_build.build(db, session_id)
    except report_build.NotGraded:
        raise HTTPException(status.HTTP_409_CONFLICT, "the session is not graded yet") from None
    if details is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    return details


@router.get("/{session_id}/report")
def get_report(session_id: uuid.UUID, db: DbSession) -> dict[str, Any]:
    """Certificates, claim map, timeline, integrity notes (not scored), AI efficiency parts."""
    return asdict(_details(db, session_id))


@router.get("/{session_id}/report/summary", response_model=SummaryOut)
def get_summary(session_id: uuid.UUID, db: DbSession) -> SummaryOut:
    """One cached generator call over the report's numbers; 503 if the model is unavailable."""
    details = _details(db, session_id)
    try:
        text = report_summary.summary(details)
    except Exception as exc:  # noqa: BLE001 - the report works without its summary
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"summary unavailable: {type(exc).__name__}"
        ) from None
    return SummaryOut(summary=text, label=report_summary.LABEL)
