"""Run, submit and auto-submit jobs with a fake runner (no Docker) and the test database."""

import json
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import grading, jobs, worker
from app.assessments import create_assessment
from app.cache import redis_client
from app.celery_app import AUTO_SUBMIT_INTERVAL_S, celery_app
from app.models import AssessmentSession, Event, FileSnapshot, Run, Score
from tests.api_support import LEAK_MARKER, portfolio
from tests.grading_support import BUGGY, FIXED, FakeRunner, tiny_spec

TASK = "tiny-add"
VISIBLE_IDS = ["tests/test_visible.py::test_adds", "tests/test_visible.py::test_zero"]


@pytest.fixture
def runner(monkeypatch) -> FakeRunner:
    fake = FakeRunner()
    monkeypatch.setattr(grading, "run_tests", fake)
    return fake


@pytest.fixture
def session_id(db: Session) -> str:
    assessment = create_assessment(db, portfolio(), "novice", [tiny_spec()])
    now = datetime.now(UTC)
    session = AssessmentSession(
        assessment_id=assessment.id,
        started_at=now,
        deadline_at=now + timedelta(minutes=60),
        status="active",
    )
    db.add(session)
    db.flush()
    return str(session.id)


def rows(db: Session, model, **where) -> list:
    stmt = select(model)
    for column, value in where.items():
        stmt = stmt.where(getattr(model, column) == value)
    return db.scalars(stmt.order_by(model.id)).all()


# --- Run ---


def test_run_stores_both_runs_and_one_event(db, runner, session_id) -> None:
    visible = grading.process_run(db, session_id, TASK, {"app/calc.py": FIXED})

    runs = rows(db, Run)
    assert [r.kind for r in runs] == ["visible", "silent"]
    assert runs[0].result["summary"] == {"passed": 2, "failed": 0, "total": 2}
    assert runs[1].result["summary"] == {"passed": 1, "failed": 0, "total": 1}
    [event] = rows(db, Event)
    assert event.type == "run"
    assert event.payload == {
        "visible": {"passed": 2, "total": 2},
        "hidden_silent": {"passed": 1, "total": 1, "failing_ids": []},
    }
    assert visible == runs[0].result


def test_failing_hidden_ids_are_recorded_but_not_returned(db, runner, session_id) -> None:
    visible = grading.process_run(db, session_id, TASK, {"app/calc.py": BUGGY})

    [event] = rows(db, Event)
    assert event.payload["hidden_silent"]["failing_ids"] == tiny_spec()["hidden_test_ids"]
    assert LEAK_MARKER not in str(visible)


def test_job_api_response_has_no_hidden_data(db, runner, session_id, client, monkeypatch):
    visible = grading.process_run(db, session_id, TASK, {"app/calc.py": BUGGY})
    job_id = str(uuid.uuid4())
    record = jobs.JobRecord(kind="run", session_id=session_id, task_id=TASK, result=visible)
    redis_client.set(f"job:{job_id}", record.model_dump_json(), ex=60)
    monkeypatch.setattr(jobs, "celery_state", lambda _id: "SUCCESS")
    try:
        response = client.get(f"/jobs/{job_id}")
    finally:
        redis_client.delete(f"job:{job_id}")

    assert response.status_code == 200
    assert response.json()["result"]["summary"]["total"] == 2
    assert LEAK_MARKER not in response.text
    assert "hidden" not in response.text


def test_visible_result_is_handed_over_before_the_hidden_run(db, runner, session_id) -> None:
    seen = []

    grading.process_run(
        db,
        session_id,
        TASK,
        {"app/calc.py": FIXED},
        on_visible=lambda result: seen.append((result["summary"]["total"], len(runner.calls))),
    )

    assert seen == [(2, 1)]  # visible result ready after the first sandbox run only
    assert len(runner.calls) == 2


def test_worker_publishes_early_and_releases_the_lock_last(db, runner, session_id, monkeypatch):
    job_id = jobs.acquire_run_lock(session_id, TASK)
    lock_held_at_publish = []
    publish = jobs.publish_run_result

    def spy(published_job_id, result):
        lock_held_at_publish.append(redis_client.get(f"run_lock:{session_id}") == job_id.encode())
        publish(published_job_id, result)

    monkeypatch.setattr(jobs, "publish_run_result", spy)
    monkeypatch.setattr(worker, "SessionLocal", lambda: nullcontext(db))
    try:
        worker.run_job.apply(args=[session_id, TASK, {"app/calc.py": FIXED}], task_id=job_id)

        assert lock_held_at_publish == [True]
        assert redis_client.get(f"run_lock:{session_id}") is None
        published = json.loads(redis_client.get(f"job:{job_id}"))["result"]
        assert published["summary"] == {"passed": 2, "failed": 0, "total": 2}
        assert [r.kind for r in rows(db, Run)] == ["visible", "silent"]
    finally:
        redis_client.delete(f"job:{job_id}", f"run_lock:{session_id}")


def test_hidden_files_never_reach_the_visible_run(db, runner, session_id) -> None:
    grading.process_run(db, session_id, TASK, {"app/calc.py": FIXED})

    visible_call, hidden_call = runner.calls
    assert not any(LEAK_MARKER in path for path in visible_call["files"])
    assert "tests/test_visible.py" not in hidden_call["files"]
    # Backend test files are read-only inside the sandbox.
    assert {"tests/test_visible.py", "tests/conftest.py", "pytest.ini"} <= visible_call["readonly"]
    assert f"tests/test_hidden_{LEAK_MARKER}.py" in hidden_call["readonly"]


def test_candidate_test_files_are_ignored_at_run_time(db, runner, session_id) -> None:
    forced_pass = "def pytest_runtest_makereport(item, call):\n    call.excinfo = None\n"
    files = {
        "app/calc.py": BUGGY,
        "conftest.py": forced_pass,
        "tests/conftest.py": forced_pass,
        "tests/test_x.py": "def test_free():\n    pass\n",
    }

    grading.process_run(db, session_id, TASK, files)

    for call in runner.calls:
        assert "conftest.py" not in call["files"]
        assert (
            call["files"]["tests/conftest.py"] == tiny_spec()["starter_files"]["tests/conftest.py"]
        )
        assert "tests/test_x.py" not in call["files"]
    visible_run = rows(db, Run, kind="visible")[0]
    assert visible_run.result["summary"]["passed"] == 0
    assert visible_run.integrity["dropped_paths"] == [
        "conftest.py",
        "tests/conftest.py",
        "tests/test_x.py",
    ]


def test_test_id_mismatch_is_an_error_not_passes(db, runner, session_id) -> None:
    runner.extra_test = True  # one more test collected than the spec expects

    visible = grading.process_run(db, session_id, TASK, {"app/calc.py": FIXED})

    assert visible["status"] == "error"
    assert visible["reason"] == "test_set_mismatch"
    assert visible["tests"] == []
    [event] = rows(db, Event)
    assert event.payload["visible"] == {"passed": 0, "total": 2}
    assert event.payload["hidden_silent"]["passed"] == 0


def test_suspicious_code_is_noted_but_still_graded(db, runner, session_id) -> None:
    files = {"app/calc.py": FIXED + "import _pytest\n"}

    grading.process_run(db, session_id, TASK, files)

    visible_run = rows(db, Run, kind="visible")[0]
    assert [f["rule"] for f in visible_run.integrity["flags"]] == ["pytest_internals"]


# --- Submit ---


def snapshot(db: Session, session_id: str, calc: str, ts: datetime) -> None:
    db.add(
        FileSnapshot(
            session_id=uuid.UUID(session_id), task_id=TASK, ts=ts, files={"app/calc.py": calc}
        )
    )
    db.flush()


def test_submit_uses_the_latest_snapshot(db, runner, session_id) -> None:
    now = datetime.now(UTC)
    snapshot(db, session_id, BUGGY, now - timedelta(minutes=5))
    snapshot(db, session_id, FIXED, now - timedelta(minutes=1))

    grading.process_submit(db, session_id)

    assert all(call["files"]["app/calc.py"] == FIXED for call in runner.calls)
    [run] = rows(db, Run, kind="submit")
    assert run.result["visible"]["summary"]["passed"] == 2
    assert run.result["hidden"]["summary"]["passed"] == 1
    [event] = rows(db, Event, type="submit")
    assert event.payload == {
        "visible": {"passed": 2, "total": 2},
        "hidden": {"passed": 1, "total": 1},
        "perf_ms": None,
        "final": True,
    }
    [score] = rows(db, Score)
    [task] = score.breakdown["tasks"]
    assert task["hidden"] == {"passed": 1, "total": 1}
    assert score.breakdown["final_score"] == 100.0
    assert db.get(AssessmentSession, uuid.UUID(session_id)).status == "submitted"


def test_submit_without_snapshot_grades_the_starter(db, runner, session_id) -> None:
    grading.process_submit(db, session_id)

    assert all(call["files"]["app/calc.py"] == BUGGY for call in runner.calls)
    [task] = rows(db, Score)[0].breakdown["tasks"]
    assert task["visible"]["passed"] == 0


def test_submit_is_idempotent(db, runner, session_id) -> None:
    grading.process_submit(db, session_id)
    calls_after_first = len(runner.calls)

    grading.process_submit(db, session_id)

    assert len(runner.calls) == calls_after_first
    assert len(rows(db, Score)) == 1
    assert len(rows(db, Run, kind="submit")) == 1
    assert len(rows(db, Event, type="submit")) == 1


# --- Auto-submit ---


def test_auto_submit_fires_for_expired_sessions_only(db, session_id, sent) -> None:
    session = db.get(AssessmentSession, uuid.UUID(session_id))
    session.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    other = create_assessment(db, portfolio(), "novice", [tiny_spec()])
    now = datetime.now(UTC)
    active = AssessmentSession(
        assessment_id=other.id, started_at=now, deadline_at=now + timedelta(minutes=5)
    )
    db.add(active)
    db.flush()

    submitted = grading.auto_submit_expired(db)

    assert submitted == [session_id]
    assert [(c["name"], c["args"]) for c in sent] == [("submit_job", [session_id])]
    db.refresh(session)
    db.refresh(active)
    assert (session.status, session.submitted_at) == ("submitted", session.deadline_at)
    assert active.status == "active"
    # A second tick finds nothing new.
    assert grading.auto_submit_expired(db) == []


def test_auto_submit_is_scheduled_every_30_seconds() -> None:
    entry = celery_app.conf.beat_schedule["auto-submit-expired"]
    assert entry == {"task": "auto_submit_expired", "schedule": AUTO_SUBMIT_INTERVAL_S}
    assert AUTO_SUBMIT_INTERVAL_S == 30
