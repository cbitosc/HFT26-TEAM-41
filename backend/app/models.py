"""Database tables. Schema changes go through an Alembic migration in migrations/versions/."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SESSION_LENGTH_MIN = 60


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("tier IN ('novice', 'adept', 'master')", name="ck_assessments_tier"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_name: Mapped[str] = mapped_column(Text)
    portfolio: Mapped[dict[str, Any]]
    tier: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="ready")
    """profiled: POST /profiles stored a Profile, tasks not built yet. ready: tasks built."""
    profile: Mapped[dict[str, Any] | None]
    """A Profile (contracts/profile.schema.json) from backend/profiler. Null if not profiled."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    """One task of an assessment. `spec` is a full TaskSpec: backend only, never sent as is."""

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("assessment_id", "task_id"),
        UniqueConstraint("assessment_id", "order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"))
    task_id: Mapped[str] = mapped_column(Text)
    """Copy of spec.task_id. URLs and events refer to tasks by it."""
    spec: Mapped[dict[str, Any]]
    order: Mapped[int] = mapped_column(Integer)


class AssessmentSession(Base):
    """A candidate's timed attempt at an assessment. One per assessment."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'submitted')", name="ck_sessions_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="active")


class FileSnapshot(Base):
    __tablename__ = "file_snapshots"
    __table_args__ = (Index("ix_file_snapshots_session_task_ts", "session_id", "task_id", "ts"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    task_id: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    files: Mapped[dict[str, Any]]


class Event(Base):
    """Append-only (enforced by a trigger, see the initial migration). Rows match event.schema."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_session_ts", "session_id", "ts"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    task_id: Mapped[str] = mapped_column(Text)
    ts: Mapped[int] = mapped_column(BigInteger)
    """Unix epoch milliseconds, as in event.schema."""
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]]


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("kind IN ('visible', 'silent', 'submit')", name="ck_runs_kind"),
        Index("ix_runs_session_task_ts", "session_id", "task_id", "ts"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    task_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16))
    result: Mapped[dict[str, Any]]
    """visible and silent: a RunResult. submit: {"visible": RunResult, "hidden": RunResult}."""
    integrity: Mapped[dict[str, Any]] = mapped_column(server_default=text("'{}'::jsonb"))
    """Report-only notes: {"dropped_paths": [...], "flags": [IntegrityFlag, ...]}. Never scored."""
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    breakdown: Mapped[dict[str, Any]]


class Interview(Base):
    """The optional AI voice interview after a submitted session (F5). Never scored.

    One per session, keyed by the session id. Audio is not stored, only the transcript.
    """

    __tablename__ = "interviews"
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'live', 'done')", name="ck_interviews_status"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    setup: Mapped[dict[str, Any]]
    """Recruiter-entered: company, role, job_description, focus."""
    plan: Mapped[dict[str, Any]]
    """interviewer.plan.Plan: questions with expected facts (backend and recruiter only)."""
    state: Mapped[dict[str, Any]]
    transcript: Mapped[list[Any]]
    status: Mapped[str] = mapped_column(String(16), default="planned")
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
