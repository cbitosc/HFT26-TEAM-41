"""Celery tasks. The app object lives in app.celery_app; the work itself in app.grading."""

import logging

from app import grading, jobs, practice, practice_jobs
from app.celery_app import celery_app
from app.db import SessionLocal

logger = logging.getLogger(__name__)

__all__ = ["celery_app"]


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="run_job", bind=True)
def run_job(self, session_id: str, task_id: str, files: dict[str, str]) -> None:
    """Publishes the visible RunResult to the job record as soon as it exists (that is
    what GET /jobs/{id} shows), then runs the hidden tests. The session's run lock is
    released only after both."""
    job_id = self.request.id
    try:
        with SessionLocal() as db:
            grading.process_run(
                db,
                session_id,
                task_id,
                files,
                on_visible=lambda result: jobs.publish_run_result(job_id, result),
            )
    finally:
        jobs.release_run_lock(session_id, job_id)


# acks_late: a job lost to a worker crash is redelivered; process_submit is idempotent.
@celery_app.task(name="submit_job", acks_late=True)
def submit_job(session_id: str) -> None:
    with SessionLocal() as db:
        grading.process_submit(db, session_id)


@celery_app.task(name="auto_submit_expired")
def auto_submit_expired() -> list[str]:
    with SessionLocal() as db:
        return grading.auto_submit_expired(db)


@celery_app.task(name="practice_job")
def practice_job(
    job_id: str,
    client_id: str,
    kind: str,
    problem_id: str,
    language: str,
    code: str,
    custom_input: dict | None,
) -> None:
    """Practice Run / Submit; the result goes into the job record that GET /practice/jobs shows."""
    practice_jobs.write(job_id, {"status": "running", "result": None, "error": None})
    try:
        if kind == "submit":
            result = practice.submit(problem_id, language, code)
        elif custom_input is not None:
            result = practice.run_custom(problem_id, language, code, custom_input)
        else:
            result = practice.run_visible(problem_id, language, code)
        practice_jobs.write(job_id, {"status": "done", "result": result, "error": None})
    except Exception:
        logger.exception("practice job %s failed", job_id)
        practice_jobs.write(job_id, {"status": "failed", "result": None, "error": "job failed"})
    finally:
        practice_jobs.release(client_id, job_id)
