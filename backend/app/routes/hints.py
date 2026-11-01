"""Hint assistant API (Adept/Master sessions only). The work is in backend/assistant."""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.models import Assessment
from app.routes.sessions import DbSession, _get_session, _get_task, _require_writable
from assistant import hints

router = APIRouter(prefix="/sessions", tags=["hints"])


class HintIn(BaseModel):
    question: str = Field(min_length=1, max_length=hints.MAX_QUESTION_CHARS)


class HintStatusOut(BaseModel):
    level: int
    """The level the next hint will have (1 concept, 2 function, 3 line)."""
    used: int
    left: int
    next_allowed_ms: int
    """Server time (ms) from which the next request is accepted; 0 when it is now."""
    rises_after_run: bool


class HintOut(BaseModel):
    reply: str
    level: int
    refused: bool
    blocked: bool
    status: HintStatusOut


def _status_out(state: hints.HintStatus) -> HintStatusOut:
    return HintStatusOut(**state.__dict__)


def _require_assistant(db: DbSession, assessment_id: uuid.UUID) -> None:
    if db.get(Assessment, assessment_id).tier not in hints.ASSISTANT_TIERS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "the assistant is for Adept and Master")


@router.get("/{session_id}/tasks/{task_id}/hints", response_model=HintStatusOut)
def hint_status(session_id: uuid.UUID, task_id: str, db: DbSession) -> HintStatusOut:
    session = _get_session(db, session_id)
    _get_task(db, session, task_id)
    _require_assistant(db, session.assessment_id)
    return _status_out(hints.hint_status(db, session.id, task_id, hints.now_ms()))


@router.post("/{session_id}/tasks/{task_id}/hint", response_model=HintOut)
def ask_hint(session_id: uuid.UUID, task_id: str, body: HintIn, db: DbSession) -> HintOut:
    session = _get_session(db, session_id)
    task = _get_task(db, session, task_id)
    _require_assistant(db, session.assessment_id)
    _require_writable(session)
    try:
        outcome = hints.request_hint(db, session.id, task, body.question)
    except hints.HintError as exc:
        headers = {"Retry-After": str(exc.retry_after_s)} if exc.retry_after_s else None
        raise HTTPException(exc.status, str(exc), headers=headers) from None
    return HintOut(
        reply=outcome.reply,
        level=outcome.level,
        refused=outcome.refused,
        blocked=outcome.blocked,
        status=_status_out(outcome.status),
    )
