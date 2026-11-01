"""Candidate session API. Every write after the deadline (or after submit) returns 409."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import jobs
from app.assessments import get_or_start_session
from app.candidate_view import to_candidate_view
from app.db import get_db
from app.models import (
    Assessment,
    AssessmentSession,
    Event,
    FileSnapshot,
    Task,
)
from app.workspace import not_editable_reason, split_editable
from contracts_gen.candidate_task_view import CandidateTaskView
from contracts_gen.event import Event as EventIn
from contracts_gen.task_spec import TaskSpec

router = APIRouter(prefix="/sessions", tags=["sessions"])

# Same key pattern as TaskSpec.starter_files (contracts/ is the source of truth).
FileMap = TaskSpec.model_fields["starter_files"].annotation

MAX_FILES = 200
MAX_FILES_BYTES = 1_000_000
MAX_EVENTS_PER_BATCH = 500
# Run, submit, hint and guard events are written by the backend itself, never accepted
# from the browser: a forged run event could fake hidden-test progress.
CLIENT_EVENT_TYPES = {"focus", "edit", "paste", "blur"}

DbSession = Annotated[Session, Depends(get_db)]


class StartSessionIn(BaseModel):
    assessment_id: uuid.UUID


class TaskRef(BaseModel):
    task_id: str
    kind: str
    order: int


class SessionOut(BaseModel):
    session_id: uuid.UUID
    assessment_id: uuid.UUID
    tier: Literal["novice", "adept", "master"]
    """The assessment's tier: Adept and Master sessions have the hint assistant."""
    status: Literal["active", "expired", "submitted"]
    """expired: past the deadline and not yet submitted (auto-submit picks it up)."""
    server_time: datetime
    started_at: datetime
    deadline_at: datetime
    submitted_at: datetime | None
    tasks: list[TaskRef]


class FilesIn(BaseModel):
    files: FileMap = Field(max_length=MAX_FILES)  # type: ignore[valid-type]

    @field_validator("files")
    @classmethod
    def total_size(cls, files: dict[str, str]) -> dict[str, str]:
        size = sum(len(p.encode()) + len(c.encode()) for p, c in files.items())
        if size > MAX_FILES_BYTES:
            raise ValueError(f"files exceed {MAX_FILES_BYTES} bytes")
        return files


class SnapshotOut(BaseModel):
    snapshot_id: int
    ts: datetime


class SavedFilesOut(BaseModel):
    snapshot_id: int | None
    """Null when nothing has been saved yet: the IDE then uses the starter files."""
    ts: datetime | None
    files: FileMap | None  # type: ignore[valid-type]


class EventsOut(BaseModel):
    accepted: int


class JobOut(BaseModel):
    job_id: str


def _now() -> datetime:
    return datetime.now(UTC)


def _get_session(db: Session, session_id: uuid.UUID) -> AssessmentSession:
    session = db.get(AssessmentSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    return session


def _get_task(db: Session, session: AssessmentSession, task_id: str) -> Task:
    task = db.scalar(
        select(Task).where(Task.assessment_id == session.assessment_id, Task.task_id == task_id)
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    return task


def _require_writable(session: AssessmentSession) -> None:
    if session.status == "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "session already submitted")
    if _now() >= session.deadline_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "session deadline has passed")


def _require_editable(task: Task, files: dict[str, str]) -> None:
    """422 listing every path the candidate may not write, with the reason for each."""
    spec = TaskSpec.model_validate(task.spec)
    refused = {path: reason for path in files if (reason := not_editable_reason(spec, path))}
    if refused:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": "these files are not editable", "paths": refused},
        )


def _session_out(db: Session, session: AssessmentSession) -> SessionOut:
    now = _now()
    state = session.status
    if state == "active" and now >= session.deadline_at:
        state = "expired"
    tasks = db.scalars(
        select(Task).where(Task.assessment_id == session.assessment_id).order_by(Task.order)
    )
    return SessionOut(
        session_id=session.id,
        assessment_id=session.assessment_id,
        tier=db.get(Assessment, session.assessment_id).tier,
        status=state,
        server_time=now,
        started_at=session.started_at,
        deadline_at=session.deadline_at,
        submitted_at=session.submitted_at,
        tasks=[TaskRef(task_id=t.task_id, kind=t.spec["kind"], order=t.order) for t in tasks],
    )


@router.post("", response_model=SessionOut)
def start_session(body: StartSessionIn, response: Response, db: DbSession) -> SessionOut:
    """Start the session for an assessment. Starting twice returns the same session (200)."""
    if db.get(Assessment, body.assessment_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "assessment not found")

    session, created = get_or_start_session(db, body.assessment_id)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return _session_out(db, session)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, db: DbSession) -> SessionOut:
    return _session_out(db, _get_session(db, session_id))


@router.get("/{session_id}/tasks/{task_id}", response_model=CandidateTaskView)
def get_task(session_id: uuid.UUID, task_id: str, db: DbSession) -> CandidateTaskView:
    task = _get_task(db, _get_session(db, session_id), task_id)
    return to_candidate_view(TaskSpec.model_validate(task.spec))


@router.get("/{session_id}/tasks/{task_id}/files", response_model=SavedFilesOut)
def get_files(session_id: uuid.UUID, task_id: str, db: DbSession) -> SavedFilesOut:
    """The candidate's latest saved files (from a save or a run), editable files only."""
    session = _get_session(db, session_id)
    task = _get_task(db, session, task_id)
    snapshot = db.scalar(
        select(FileSnapshot)
        .where(FileSnapshot.session_id == session.id, FileSnapshot.task_id == task_id)
        .order_by(FileSnapshot.ts.desc(), FileSnapshot.id.desc())
        .limit(1)
    )
    if snapshot is None:
        return SavedFilesOut(snapshot_id=None, ts=None, files=None)
    editable, _ = split_editable(TaskSpec.model_validate(task.spec), snapshot.files)
    return SavedFilesOut(snapshot_id=snapshot.id, ts=snapshot.ts, files=editable)


@router.put("/{session_id}/tasks/{task_id}/files", response_model=SnapshotOut)
def save_files(session_id: uuid.UUID, task_id: str, body: FilesIn, db: DbSession) -> SnapshotOut:
    session = _get_session(db, session_id)
    task = _get_task(db, session, task_id)
    _require_writable(session)
    _require_editable(task, body.files)
    snapshot = FileSnapshot(session_id=session.id, task_id=task_id, ts=_now(), files=body.files)
    db.add(snapshot)
    db.commit()
    return SnapshotOut(snapshot_id=snapshot.id, ts=snapshot.ts)


@router.post("/{session_id}/events", response_model=EventsOut)
def post_events(
    session_id: uuid.UUID,
    db: DbSession,
    events: Annotated[list[EventIn], Body(max_length=MAX_EVENTS_PER_BATCH)],
) -> EventsOut:
    """Store a batch of telemetry events. The whole batch is rejected if any event is bad."""
    session = _get_session(db, session_id)
    _require_writable(session)
    task_ids = set(
        db.scalars(select(Task.task_id).where(Task.assessment_id == session.assessment_id))
    )

    rows = []
    for i, wrapped in enumerate(events):
        event = wrapped.root
        if event.type not in CLIENT_EVENT_TYPES:
            raise HTTPException(422, f"event {i}: type {event.type!r} is not accepted from clients")
        if event.session_id != str(session.id):
            raise HTTPException(422, f"event {i}: session_id does not match the URL")
        if event.task_id not in task_ids:
            raise HTTPException(422, f"event {i}: unknown task_id {event.task_id!r}")
        rows.append(
            Event(
                session_id=session.id,
                task_id=event.task_id,
                ts=event.ts,
                type=event.type,
                payload=event.payload.model_dump(mode="json"),
            )
        )
    db.add_all(rows)
    db.commit()
    return EventsOut(accepted=len(rows))


@router.post("/{session_id}/tasks/{task_id}/run", response_model=JobOut)
def run_task(session_id: uuid.UUID, task_id: str, body: FilesIn, db: DbSession) -> JobOut:
    """Autosave the files, then enqueue a run of the visible (and, silently, hidden) tests.

    One run per session at a time: 429 while the previous one is queued or running.
    """
    session = _get_session(db, session_id)
    task = _get_task(db, session, task_id)
    _require_writable(session)
    _require_editable(task, body.files)
    try:
        job_id = jobs.acquire_run_lock(str(session.id), task_id)
    except jobs.RunInProgress:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "a run is already in progress for this session"
        ) from None
    try:
        db.add(FileSnapshot(session_id=session.id, task_id=task_id, ts=_now(), files=body.files))
        db.commit()
        jobs.send_job(
            job_id,
            "run_job",
            [str(session.id), task_id, body.files],
            jobs.JobRecord(kind="run", session_id=str(session.id), task_id=task_id),
        )
    except Exception:
        jobs.release_run_lock(str(session.id), job_id)
        raise
    return JobOut(job_id=job_id)


@router.post("/{session_id}/submit", response_model=JobOut)
def submit_session(session_id: uuid.UUID, db: DbSession) -> JobOut:
    """Lock the session and enqueue full grading."""
    session = _get_session(db, session_id)
    _require_writable(session)
    session.status = "submitted"
    session.submitted_at = _now()
    db.commit()
    return JobOut(job_id=jobs.enqueue_submit(str(session.id)))
