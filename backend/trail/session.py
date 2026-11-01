"""Load a session's Trail Map from stored records: task specs, events and snapshots."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssessmentSession, Event, FileSnapshot, Task
from app.workspace import split_editable
from contracts_gen.task_spec import TaskSpec
from trail.replay import Edit, Focus, Hint, TaskTrail, build_trail

CODE_SUFFIXES = (".py", ".js")


def _ms(moment) -> int:
    return int(moment.timestamp() * 1000)


def _code(spec: TaskSpec, files: dict[str, str]) -> dict[str, str]:
    editable, _ = split_editable(spec, files)
    return {p: c for p, c in editable.items() if p.endswith(CODE_SUFFIXES)}


def session_trail(db: Session, session: AssessmentSession) -> list[TaskTrail]:
    tasks = db.scalars(
        select(Task).where(Task.assessment_id == session.assessment_id).order_by(Task.order)
    ).all()
    events = db.scalars(
        select(Event)
        .where(
            Event.session_id == session.id,
            Event.type.in_(("focus", "edit", "hint_response")),
        )
        .order_by(Event.ts, Event.id)
    ).all()
    snapshots = db.scalars(
        select(FileSnapshot)
        .where(FileSnapshot.session_id == session.id)
        .order_by(FileSnapshot.ts, FileSnapshot.id)
    ).all()
    return [_task_trail(TaskSpec.model_validate(t.spec), events, snapshots) for t in tasks]


def _task_trail(spec: TaskSpec, events, snapshots) -> TaskTrail:
    task_events = [e for e in events if e.task_id == spec.task_id]
    starter = _code(spec, spec.starter_files)
    task_snapshots = [
        (_ms(s.ts), _code(spec, s.files)) for s in snapshots if s.task_id == spec.task_id
    ]
    final = starter | (task_snapshots[-1][1] if task_snapshots else {})
    targets = list(spec.target_symbols or spec.entry_symbols)
    return build_trail(
        task_id=spec.task_id,
        kind=spec.kind,
        starter=starter,
        targets=targets,
        focus=[
            Focus(e.ts, e.payload["file"], e.payload["line"])
            for e in task_events
            if e.type == "focus"
        ],
        edits=[
            Edit(e.ts, e.payload["file"], e.payload["chars_added"] + e.payload["chars_removed"])
            for e in task_events
            if e.type == "edit"
        ],
        snapshots=task_snapshots,
        hints=[
            Hint(e.ts, e.payload["level"], e.payload["blocked"])
            for e in task_events
            if e.type == "hint_response"
        ],
        final=final,
    )


def load(db: Session, session_id: uuid.UUID) -> list[TaskTrail] | None:
    session = db.get(AssessmentSession, session_id)
    return None if session is None else session_trail(db, session)
