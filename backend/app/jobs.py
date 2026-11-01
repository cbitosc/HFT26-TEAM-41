"""Enqueue Celery jobs and report their status to the API.

Each job gets a small record in Redis ({kind, session_id, task_id, result}), so
GET /jobs/{id} answers 404 for ids we never issued instead of Celery's "PENDING forever".
A run job publishes its visible RunResult into the record as soon as the visible run
finishes; the job stays "running" until the hidden run is stored too.
A session has at most one run job in flight, guarded by a Redis lock holding its job id.
"""

import json
import logging
import uuid
from typing import Any, Literal

from celery.result import AsyncResult
from pydantic import BaseModel, ValidationError

from app.cache import redis_client
from app.celery_app import celery_app
from contracts_gen.run_result import RunResult

logger = logging.getLogger(__name__)

JobKind = Literal["run", "submit"]
JobStatus = Literal["queued", "running", "done", "failed"]

JOB_RECORD_TTL_S = 24 * 3600
# Longer than a run job can take (two sandbox runs); a crashed worker frees it this way.
RUN_LOCK_TTL_S = 300

_STATUS = {
    "PENDING": "queued",
    "RECEIVED": "queued",
    "STARTED": "running",
    "RETRY": "running",
    "SUCCESS": "done",
    "FAILURE": "failed",
    "REVOKED": "failed",
}


class RunInProgress(Exception):
    """The session already has a run job queued or running."""


class JobRecord(BaseModel):
    kind: JobKind
    session_id: str
    task_id: str | None
    result: dict[str, Any] | None = None
    """Visible RunResult of a run job, published before the hidden run."""


class JobView(BaseModel):
    job_id: str
    kind: JobKind
    status: JobStatus
    """done/failed: the whole job has finished and the session may Run again."""
    result: RunResult | None
    """Visible RunResult of a run job, shown as soon as it exists (status may still be
    "running" while hidden tests run). Null otherwise."""
    error: str | None


def new_job_id() -> str:
    return str(uuid.uuid4())


def send_job(job_id: str, task_name: str, args: list[Any], record: JobRecord) -> None:
    # Record first, so a fast worker can't finish a job we don't know about yet.
    redis_client.set(f"job:{job_id}", record.model_dump_json(), ex=JOB_RECORD_TTL_S)
    celery_app.send_task(task_name, args=args, task_id=job_id)


def enqueue_submit(session_id: str) -> str:
    job_id = new_job_id()
    send_job(
        job_id,
        "submit_job",
        [session_id],
        JobRecord(kind="submit", session_id=session_id, task_id=None),
    )
    return job_id


def _run_lock(session_id: str) -> str:
    return f"run_lock:{session_id}"


def acquire_run_lock(session_id: str, task_id: str) -> str:
    """Reserve the session's single run slot; returns the job id to use for the run.

    The job record is written before the lock, so a holder without a record is truly
    stale. Raises RunInProgress if the current holder is still queued or running.
    """
    job_id = new_job_id()
    record = JobRecord(kind="run", session_id=session_id, task_id=task_id)
    redis_client.set(f"job:{job_id}", record.model_dump_json(), ex=JOB_RECORD_TTL_S)
    key = _run_lock(session_id)
    if redis_client.set(key, job_id, nx=True, ex=RUN_LOCK_TTL_S):
        return job_id
    holder = redis_client.get(key)
    job = get_job(holder.decode()) if holder else None
    if job is not None and job.status in ("queued", "running"):
        redis_client.delete(f"job:{job_id}")
        raise RunInProgress
    # The holder finished without releasing (or its record expired): take over.
    redis_client.set(key, job_id, ex=RUN_LOCK_TTL_S)
    return job_id


def release_run_lock(session_id: str, job_id: str) -> None:
    key = _run_lock(session_id)
    if redis_client.get(key) == job_id.encode():
        redis_client.delete(key)


def publish_run_result(job_id: str, result: dict[str, Any]) -> None:
    """Store a run job's visible RunResult in its record (the only result the API shows)."""
    raw = redis_client.get(f"job:{job_id}")
    if raw is None:
        logger.error("No record for job %s; visible result not published", job_id)
        return
    record = JobRecord.model_validate(json.loads(raw)).model_copy(update={"result": result})
    redis_client.set(f"job:{job_id}", record.model_dump_json(), ex=JOB_RECORD_TTL_S)


def celery_state(job_id: str) -> str:
    return AsyncResult(job_id, app=celery_app).state


def get_job(job_id: str) -> JobView | None:
    raw = redis_client.get(f"job:{job_id}")
    if raw is None:
        return None
    record = JobRecord.model_validate(json.loads(raw))
    status: JobStatus = _STATUS.get(celery_state(job_id), "queued")

    result = None
    error = "job failed" if status == "failed" else None
    if record.kind == "run" and record.result is not None:
        # Only a valid visible RunResult is passed on; anything else is withheld.
        try:
            result = RunResult.model_validate(record.result)
        except ValidationError:
            logger.error("Job %s published something other than a RunResult", job_id)
            status, error = "failed", "job failed"
    elif record.kind == "run" and status == "done":
        logger.error("Run job %s finished without publishing a result", job_id)
        status, error = "failed", "job failed"
    return JobView(job_id=job_id, kind=record.kind, status=status, result=result, error=error)
