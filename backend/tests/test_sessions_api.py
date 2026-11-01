"""Session routes against a real (test) Postgres. Celery is replaced by a recorder."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import jobs
from app.assessments import create_assessment
from app.models import AssessmentSession, Event, FileSnapshot
from contracts_gen.candidate_task_view import CandidateTaskView
from tests.api_support import LEAK_MARKER, domain_spec, dsa_spec, leaky, portfolio

DOMAIN_ID = "fastapi-inventory-low-stock"
DSA_ID = "dsa-longest-unique-substring"
# Only starter files are editable: app/main.py in the domain task, solution.py in the DSA one.
FILES = {"app/main.py": "print('hi')\n"}
DSA_FILES = {"solution.py": "def f():\n    return 1\n"}


@pytest.fixture
def assessment_id(db: Session) -> str:
    return str(create_assessment(db, portfolio(), "master", [domain_spec(), dsa_spec()]).id)


@pytest.fixture
def session_id(http: TestClient, assessment_id: str) -> str:
    return http.post("/sessions", json={"assessment_id": assessment_id}).json()["session_id"]


def edit_event(session_id: str, task_id: str = DOMAIN_ID) -> dict:
    event = {
        "session_id": session_id,
        "task_id": task_id,
        "ts": 1793352695000,
        "type": "edit",
        "payload": {"file": "app/main.py", "symbol": None, "chars_added": 3, "chars_removed": 0},
    }
    return event


def expire(db: Session, session_id: str) -> None:
    session = db.get(AssessmentSession, uuid.UUID(session_id))
    session.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()


def count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# --- POST /sessions, GET /sessions/{id} ---


def test_start_session_sets_a_60_minute_server_deadline(http, assessment_id) -> None:
    response = http.post("/sessions", json={"assessment_id": assessment_id})

    assert response.status_code == 201
    body = response.json()
    started = datetime.fromisoformat(body["started_at"])
    assert datetime.fromisoformat(body["deadline_at"]) - started == timedelta(minutes=60)
    assert body["status"] == "active"
    assert [t["task_id"] for t in body["tasks"]] == [DOMAIN_ID, DSA_ID]
    assert [t["kind"] for t in body["tasks"]] == ["domain", "dsa"]


def test_starting_twice_returns_the_same_session(http, assessment_id) -> None:
    first = http.post("/sessions", json={"assessment_id": assessment_id})
    second = http.post("/sessions", json={"assessment_id": assessment_id})

    assert second.status_code == 200
    assert second.json()["session_id"] == first.json()["session_id"]
    assert second.json()["deadline_at"] == first.json()["deadline_at"]


def test_start_unknown_assessment_is_404(http) -> None:
    response = http.post(
        "/sessions", json={"assessment_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 404


def test_get_session_reports_server_time_and_deadline(http, session_id) -> None:
    body = http.get(f"/sessions/{session_id}").json()

    server_time = datetime.fromisoformat(body["server_time"])
    assert abs(server_time - datetime.now(UTC)) < timedelta(seconds=5)
    assert body["status"] == "active"
    assert len(body["tasks"]) == 2


def test_get_session_after_deadline_is_expired(http, db, session_id) -> None:
    expire(db, session_id)
    assert http.get(f"/sessions/{session_id}").json()["status"] == "expired"


def test_get_unknown_session_is_404(http) -> None:
    assert http.get("/sessions/00000000-0000-0000-0000-000000000000").status_code == 404


# --- GET /sessions/{id}/tasks/{task_id} ---


@pytest.mark.parametrize("task_id", [DOMAIN_ID, DSA_ID])
def test_task_route_returns_candidate_view(http, session_id, task_id) -> None:
    response = http.get(f"/sessions/{session_id}/tasks/{task_id}")

    assert response.status_code == 200
    view = CandidateTaskView.model_validate(response.json())
    assert view.task_id == task_id


def test_task_route_never_leaks_backend_only_data(http, db) -> None:
    assessment = create_assessment(
        db, portfolio(), "master", [leaky(domain_spec()), leaky(dsa_spec())]
    )
    session_id = http.post("/sessions", json={"assessment_id": str(assessment.id)}).json()[
        "session_id"
    ]

    for task_id in (DOMAIN_ID, DSA_ID):
        response = http.get(f"/sessions/{session_id}/tasks/{task_id}")
        assert response.status_code == 200
        assert LEAK_MARKER not in response.text
        assert "reference_ref" not in response.text
        assert "hidden" not in response.json()
        assert "certificate" not in response.json()


def test_unknown_task_is_404(http, session_id) -> None:
    assert http.get(f"/sessions/{session_id}/tasks/nope").status_code == 404


# --- PUT files ---


def test_save_files_stores_a_snapshot(http, db, session_id) -> None:
    response = http.put(f"/sessions/{session_id}/tasks/{DOMAIN_ID}/files", json={"files": FILES})

    assert response.status_code == 200
    snapshot = db.get(FileSnapshot, response.json()["snapshot_id"])
    assert snapshot.files == FILES
    assert snapshot.task_id == DOMAIN_ID


# --- GET files ---


def test_get_files_before_any_save_is_empty(http, session_id) -> None:
    response = http.get(f"/sessions/{session_id}/tasks/{DOMAIN_ID}/files")

    assert response.status_code == 200
    assert response.json() == {"snapshot_id": None, "ts": None, "files": None}


def test_get_files_returns_the_latest_snapshot_of_that_task(http, session_id) -> None:
    url = f"/sessions/{session_id}/tasks/{DOMAIN_ID}/files"
    http.put(url, json={"files": FILES})
    latest = http.put(url, json={"files": {"app/main.py": "print('v2')\n"}}).json()
    http.put(f"/sessions/{session_id}/tasks/{DSA_ID}/files", json={"files": DSA_FILES})

    body = http.get(url).json()

    assert body["snapshot_id"] == latest["snapshot_id"]
    assert body["files"] == {"app/main.py": "print('v2')\n"}
    assert http.get(f"/sessions/{session_id}/tasks/{DSA_ID}/files").json()["files"] == DSA_FILES


def test_get_files_returns_only_editable_files(http, db, session_id) -> None:
    # Snapshots written by the backend itself could hold more; the allowlist still applies.
    db.add(
        FileSnapshot(
            session_id=uuid.UUID(session_id),
            task_id=DOMAIN_ID,
            ts=datetime.now(UTC),
            files={**FILES, "tests/test_x.py": "x", "conftest.py": "x", "new.py": "x"},
        )
    )
    db.flush()

    assert http.get(f"/sessions/{session_id}/tasks/{DOMAIN_ID}/files").json()["files"] == FILES


def test_get_files_still_works_after_the_deadline(http, db, session_id) -> None:
    http.put(f"/sessions/{session_id}/tasks/{DOMAIN_ID}/files", json={"files": FILES})
    expire(db, session_id)

    assert http.get(f"/sessions/{session_id}/tasks/{DOMAIN_ID}/files").json()["files"] == FILES


@pytest.mark.parametrize("path", ["unknown-task", "nope"])
def test_get_files_unknown_task_is_404(http, session_id, path) -> None:
    assert http.get(f"/sessions/{session_id}/tasks/{path}/files").status_code == 404


@pytest.mark.parametrize("path", ["../etc/passwd", "/abs.py", "a/../b.py"])
def test_save_files_rejects_unsafe_paths(http, session_id, path) -> None:
    response = http.put(
        f"/sessions/{session_id}/tasks/{DOMAIN_ID}/files", json={"files": {path: ""}}
    )
    assert response.status_code == 422


def test_save_files_rejects_oversized_payload(http, session_id) -> None:
    files = {"big.py": "x" * 1_000_001}
    response = http.put(f"/sessions/{session_id}/tasks/{DOMAIN_ID}/files", json={"files": files})
    assert response.status_code == 422


# --- POST events ---


def test_events_batch_is_stored(http, db, session_id) -> None:
    batch = [
        edit_event(session_id),
        {
            "session_id": session_id,
            "task_id": DSA_ID,
            "ts": 1793352696000,
            "type": "focus",
            "payload": {"file": "solution.py", "line": 3, "symbol": None},
        },
        {
            "session_id": session_id,
            "task_id": DSA_ID,
            "ts": 1793352697000,
            "type": "blur",
            "payload": {},
        },
    ]

    response = http.post(f"/sessions/{session_id}/events", json=batch)

    assert response.status_code == 200
    assert response.json() == {"accepted": 3}
    rows = db.scalars(select(Event).order_by(Event.ts)).all()
    assert [r.type for r in rows] == ["edit", "focus", "blur"]
    assert rows[0].payload == batch[0]["payload"]


@pytest.mark.parametrize(
    "bad",
    [
        {"payload": {"file": "app/main.py"}},  # schema: payload incomplete
        {"type": "teleport"},  # schema: unknown type
        {"task_id": "not-in-this-assessment"},
        {"session_id": "00000000-0000-0000-0000-000000000000"},
        # Server-written types are refused from clients.
        {
            "type": "run",
            "payload": {
                "visible": {"passed": 9, "total": 9},
                "hidden_silent": {"passed": 30, "total": 30, "failing_ids": []},
            },
        },
    ],
    ids=["bad-payload", "unknown-type", "unknown-task", "other-session", "client-run-event"],
)
def test_bad_event_rejects_the_whole_batch(http, db, session_id, bad) -> None:
    batch = [edit_event(session_id), edit_event(session_id) | bad]

    response = http.post(f"/sessions/{session_id}/events", json=batch)

    assert response.status_code == 422
    assert count(db, Event) == 0


def test_events_are_append_only(http, db, session_id) -> None:
    http.post(f"/sessions/{session_id}/events", json=[edit_event(session_id)])

    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("UPDATE events SET type = 'paste'"))
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("DELETE FROM events"))


# --- POST run, POST submit ---


def test_run_saves_files_and_enqueues_a_job(http, db, session_id, sent) -> None:
    response = http.post(f"/sessions/{session_id}/tasks/{DSA_ID}/run", json={"files": DSA_FILES})

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert sent == [{"name": "run_job", "args": [session_id, DSA_ID, DSA_FILES], "task_id": job_id}]
    assert count(db, FileSnapshot) == 1


def test_submit_locks_the_session_and_enqueues_grading(http, session_id, sent) -> None:
    response = http.post(f"/sessions/{session_id}/submit")

    assert response.status_code == 200
    assert sent[0]["name"] == "submit_job" and sent[0]["args"] == [session_id]
    assert http.get(f"/sessions/{session_id}").json()["status"] == "submitted"
    assert http.post(f"/sessions/{session_id}/submit").status_code == 409
    assert (
        http.post(f"/sessions/{session_id}/events", json=[edit_event(session_id)]).status_code
        == 409
    )


# --- Deadline ---

WRITES = {
    "save-files": ("put", f"/tasks/{DOMAIN_ID}/files", {"files": FILES}),
    "events": ("post", "/events", None),
    "run": ("post", f"/tasks/{DOMAIN_ID}/run", {"files": FILES}),
    "submit": ("post", "/submit", None),
}


@pytest.mark.parametrize("write", WRITES.values(), ids=WRITES.keys())
def test_every_write_after_deadline_is_409(http, db, session_id, sent, write) -> None:
    method, path, body = write
    if path == "/events":
        body = [edit_event(session_id)]
    expire(db, session_id)

    response = http.request(method, f"/sessions/{session_id}{path}", json=body)

    assert response.status_code == 409
    assert sent == []
    assert count(db, Event) == count(db, FileSnapshot) == 0
    assert db.get(AssessmentSession, uuid.UUID(session_id)).status == "active"


# --- Anti-tampering, concurrency, ids ---


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("tests/test_x.py", "test directories are read-only"),
        ("conftest.py", "test or package configuration"),
        ("app/new_module.py", "only files in the task's starter code"),
    ],
)
def test_save_rejects_files_outside_the_editable_allowlist(http, db, session_id, path, reason):
    files = {"app/main.py": "ok = 1\n", path: "x = 1\n"}

    response = http.put(f"/sessions/{session_id}/tasks/{DOMAIN_ID}/files", json={"files": files})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert list(detail["paths"]) == [path]
    assert reason in detail["paths"][path]
    assert count(db, FileSnapshot) == 0


def test_run_rejects_files_outside_the_editable_allowlist(http, session_id, sent) -> None:
    files = {"solution.py": "x = 1\n", "conftest.py": "x = 1\n"}

    response = http.post(f"/sessions/{session_id}/tasks/{DSA_ID}/run", json={"files": files})

    assert response.status_code == 422
    assert sent == []


def test_second_run_while_one_is_queued_is_429(http, session_id, sent, monkeypatch) -> None:
    url = f"/sessions/{session_id}/tasks/{DSA_ID}/run"

    first = http.post(url, json={"files": DSA_FILES})
    second = http.post(url, json={"files": DSA_FILES})

    assert first.status_code == 200
    assert second.status_code == 429
    assert len(sent) == 1

    # Once the first job has finished, the next Run is accepted.
    monkeypatch.setattr(jobs, "celery_state", lambda _id: "SUCCESS")
    assert http.post(url, json={"files": DSA_FILES}).status_code == 200


def test_session_ids_are_random_uuid4(http, db) -> None:
    ids = []
    for _ in range(3):
        assessment = create_assessment(db, portfolio(), "novice", [dsa_spec()])
        body = http.post("/sessions", json={"assessment_id": str(assessment.id)}).json()
        ids.append(uuid.UUID(body["session_id"]))

    assert all(session_id.version == 4 for session_id in ids)
    assert len({session_id.int for session_id in ids}) == 3
    # Not sequential: neighbouring ids differ in far more than the last digit.
    assert all(abs(a.int - b.int) > 2**64 for a, b in zip(ids, ids[1:], strict=False))
