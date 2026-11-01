"""Trail Map API (recruiter key): the session's function graph, replay and metrics."""

import uuid
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.recruiter import require_recruiter
from app.routes.sessions import DbSession
from trail import session as trail_session

router = APIRouter(prefix="/sessions", tags=["trail"], dependencies=[Depends(require_recruiter)])


class TrailNode(BaseModel):
    id: str
    """"path::qualname" (as in TaskSpec.target_symbols), or "path" for code outside functions."""
    file: str
    name: str
    target: bool
    start: int | None
    end: int | None
    dwell_ms: int


class TrailVisit(BaseModel):
    node: str
    start_ms: int
    end_ms: int
    after_hint: bool


class TrailEdit(BaseModel):
    ts: int
    node: str
    chars: int


class TrailHint(BaseModel):
    ts: int
    level: int
    blocked: bool


class TrailMetrics(BaseModel):
    time_to_target_ms: int | None
    off_path_ms: int
    found: Literal["independent", "after_hint", "not_found"]
    edit_precision: float | None
    lines_changed: int
    functions_visited: int
    hints: int


class TaskTrailOut(BaseModel):
    task_id: str
    kind: str
    targets: list[str]
    files: list[str]
    nodes: list[TrailNode]
    edges: list[tuple[str, str]]
    visits: list[TrailVisit]
    edits: list[TrailEdit]
    hints: list[TrailHint]
    metrics: TrailMetrics
    first_ms: int | None
    last_ms: int | None


class TrailOut(BaseModel):
    session_id: uuid.UUID
    tasks: list[TaskTrailOut]


@router.get("/{session_id}/trail", response_model=TrailOut)
def get_trail(session_id: uuid.UUID, db: DbSession) -> TrailOut:
    """Report-only: never part of the score (CLAUDE.md rule 8)."""
    trails = trail_session.load(db, session_id)
    if trails is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    return TrailOut(
        session_id=session_id,
        tasks=[TaskTrailOut.model_validate(asdict(t)) for t in trails],
    )
