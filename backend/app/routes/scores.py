"""Session scores for the report: the latest stored score, and a re-grade from stored records."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AssessmentSession, Score
from contracts_gen.score_breakdown import ScoreBreakdown
from scoring.score_session import score_session

router = APIRouter(prefix="/sessions", tags=["scores"])

DbSession = Annotated[Session, Depends(get_db)]


class ScoreOut(BaseModel):
    status: Literal["in_progress", "grading", "graded"]
    """in_progress: not submitted yet. grading: submitted, the submit job hasn't finished."""
    computed_at: datetime | None
    breakdown: ScoreBreakdown | None


def _session(db: Session, session_id: uuid.UUID) -> AssessmentSession:
    session = db.get(AssessmentSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    return session


def _latest_score(db: Session, session_id: uuid.UUID) -> Score | None:
    return db.scalars(
        select(Score)
        .where(Score.session_id == session_id)
        .order_by(Score.computed_at.desc(), Score.id.desc())
        .limit(1)
    ).first()


@router.get("/{session_id}/score", response_model=ScoreOut)
def get_score(session_id: uuid.UUID, db: DbSession) -> ScoreOut:
    session = _session(db, session_id)
    score = _latest_score(db, session.id)
    if score is not None:
        return ScoreOut(status="graded", computed_at=score.computed_at, breakdown=score.breakdown)
    state = "grading" if session.status == "submitted" else "in_progress"
    return ScoreOut(status=state, computed_at=None, breakdown=None)


@router.post("/{session_id}/regrade", response_model=ScoreBreakdown)
def regrade(session_id: uuid.UUID, db: DbSession) -> ScoreBreakdown:
    """Recompute the score from the stored submit runs and events (no sandbox, no LLM) and
    store it as the latest score. The same records always give byte-identical JSON."""
    session = _session(db, session_id)
    if _latest_score(db, session.id) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "session has not been graded yet")
    breakdown = score_session(db, session.id)
    db.add(
        Score(
            session_id=session.id,
            computed_at=datetime.now(UTC),
            breakdown=breakdown.model_dump(mode="json"),
        )
    )
    db.commit()
    return breakdown
