"""GET /jobs/{id}: status mapping and visible-results-only output. Celery state is faked."""

import json
import uuid

import pytest

from app import jobs
from app.cache import redis_client
from tests.api_support import fixture

RUN_RESULT = fixture("run_result.valid.json")


@pytest.fixture
def job_id() -> str:
    job_id = f"test-{uuid.uuid4()}"
    record = jobs.JobRecord(kind="run", session_id="s", task_id="t")
    redis_client.set(f"job:{job_id}", record.model_dump_json(), ex=60)
    yield job_id
    redis_client.delete(f"job:{job_id}")


def fake_state(monkeypatch, state: str) -> None:
    monkeypatch.setattr(jobs, "celery_state", lambda _id: state)


def test_unknown_job_is_404(client) -> None:
    assert client.get(f"/jobs/{uuid.uuid4()}").status_code == 404


@pytest.mark.parametrize(
    ("state", "status"),
    [("PENDING", "queued"), ("STARTED", "running"), ("FAILURE", "failed")],
)
def test_status_mapping(client, monkeypatch, job_id, state, status) -> None:
    fake_state(monkeypatch, state)

    body = client.get(f"/jobs/{job_id}").json()

    assert body["status"] == status
    assert body["result"] is None
    assert body["error"] == ("job failed" if status == "failed" else None)


def test_visible_result_is_shown_while_hidden_tests_still_run(client, monkeypatch, job_id):
    fake_state(monkeypatch, "STARTED")
    jobs.publish_run_result(job_id, RUN_RESULT)

    body = client.get(f"/jobs/{job_id}").json()

    assert (body["status"], body["result"]) == ("running", RUN_RESULT)


def test_finished_run_returns_the_visible_run_result(client, monkeypatch, job_id) -> None:
    fake_state(monkeypatch, "SUCCESS")
    jobs.publish_run_result(job_id, RUN_RESULT)

    body = client.get(f"/jobs/{job_id}").json()

    assert (body["status"], body["result"], body["error"]) == ("done", RUN_RESULT, None)


def test_finished_run_without_a_published_result_is_failed(client, monkeypatch, job_id):
    fake_state(monkeypatch, "SUCCESS")

    body = client.get(f"/jobs/{job_id}").json()

    assert (body["status"], body["result"]) == ("failed", None)


def test_result_with_extra_data_is_withheld(client, monkeypatch, job_id) -> None:
    fake_state(monkeypatch, "SUCCESS")
    jobs.publish_run_result(job_id, RUN_RESULT | {"hidden_silent": {"passed": 1, "total": 2}})

    body = client.get(f"/jobs/{job_id}").json()

    assert body["status"] == "failed"
    assert body["result"] is None
    assert "hidden" not in str(body)


def test_publish_keeps_the_record_and_its_ttl(job_id) -> None:
    jobs.publish_run_result(job_id, RUN_RESULT)

    record = json.loads(redis_client.get(f"job:{job_id}"))
    assert record == {"kind": "run", "session_id": "s", "task_id": "t", "result": RUN_RESULT}
    assert redis_client.ttl(f"job:{job_id}") > 60


def test_enqueue_records_the_job_before_sending(monkeypatch) -> None:
    sent = []
    monkeypatch.setattr(
        jobs.celery_app,
        "send_task",
        lambda name, args, task_id: sent.append((name, redis_client.exists(f"job:{task_id}"))),
    )

    job_id = jobs.enqueue_submit("s")

    try:
        assert sent == [("submit_job", 1)]
        assert jobs.get_job(job_id) is not None
    finally:
        redis_client.delete(f"job:{job_id}")


def test_run_lock_is_released_only_by_its_own_job() -> None:
    session_id = f"test-{uuid.uuid4()}"
    job_ids = [jobs.acquire_run_lock(session_id, "t")]
    try:
        jobs.release_run_lock(session_id, "someone-else")
        # The holder's record exists and its job hasn't run: still in progress.
        with pytest.raises(jobs.RunInProgress):
            jobs.acquire_run_lock(session_id, "t")

        jobs.release_run_lock(session_id, job_ids[0])
        job_ids.append(jobs.acquire_run_lock(session_id, "t"))
    finally:
        redis_client.delete(f"run_lock:{session_id}", *(f"job:{j}" for j in job_ids))
