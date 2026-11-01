import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SESSION_LENGTH_MIN, Assessment, AssessmentSession, Task
from contracts_gen.portfolio import Portfolio
from contracts_gen.task_spec import TaskSpec


def create_assessment(
    db: Session, portfolio: dict[str, Any], tier: str, specs: list[dict[str, Any]]
) -> Assessment:
    """Store an assessment and its tasks (in the given order). Validates against contracts/."""
    validated = Portfolio.model_validate(portfolio)
    assessment = Assessment(
        candidate_name=validated.basics.name,
        portfolio=portfolio,
        tier=tier,
        status="ready",
    )
    db.add(assessment)
    db.flush()
    for order, spec in enumerate(specs):
        task_spec = TaskSpec.model_validate(spec)
        db.add(Task(assessment_id=assessment.id, task_id=task_spec.task_id, spec=spec, order=order))
    db.flush()
    return assessment


def get_or_start_session(db: Session, assessment_id: uuid.UUID) -> tuple[AssessmentSession, bool]:
    """(the assessment's session, whether it was created now). Commits a new session.

    The server sets the deadline: now + 60 min. One session per assessment, so starting
    twice returns the same session, even when two requests race.
    """
    by_assessment = select(AssessmentSession).where(
        AssessmentSession.assessment_id == assessment_id
    )
    session = db.scalar(by_assessment)
    if session is not None:
        return session, False
    now = datetime.now(UTC)
    session = AssessmentSession(
        assessment_id=assessment_id,
        started_at=now,
        deadline_at=now + timedelta(minutes=SESSION_LENGTH_MIN),
        status="active",
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request started it first (unique assessment_id).
        db.rollback()
        return db.scalars(by_assessment).one(), False
    return session, True
