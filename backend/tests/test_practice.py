"""Practice mode: problem listing, job limits, input validation and result shaping.

The sandbox is faked (app.dsa.run_cases / execute_cases); real runs are covered by the
DSA docker tests.
"""

import uuid

import pytest

from app import dsa, practice, practice_jobs
from app.cache import redis_client
from app.routes import practice as routes
from builder.dsa_bank import load_bank
from runner import ProgramRun

CLIENT = "client-" + uuid.uuid4().hex[:12]
CODE = "def three_sum(nums):\n    return []\n"


@pytest.fixture
def sent(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        routes.celery_app,
        "send_task",
        lambda name, args, task_id: calls.append({"name": name, "args": args, "task_id": task_id}),
    )
    yield calls
    for call in calls:
        redis_client.delete(f"practice:job:{call['task_id']}")
    redis_client.delete(f"practice:lock:{CLIENT}")
    for key in redis_client.scan_iter(f"practice:rate:{CLIENT}:*"):
        redis_client.delete(key)


def headers(client_id: str = CLIENT) -> dict[str, str]:
    return {"X-Client-Id": client_id}


def test_list_is_sorted_by_difficulty(client) -> None:
    problems = client.get("/practice/problems").json()
    assert any(p["id"] == "3sum" for p in problems)
    ranks = [{"easy": 0, "medium": 1, "hard": 2}[p["difficulty"]] for p in problems]
    assert ranks == sorted(ranks)
    assert {"id", "title", "difficulty", "tags"} == set(problems[0])


def test_only_practice_only_problems_are_listed_or_served(client, sent) -> None:
    listed = {p["id"] for p in client.get("/practice/problems").json()}
    assert listed == {p.id for p in load_bank() if p.practice_only}
    assessment = next(p.id for p in load_bank() if not p.practice_only)
    body = {"language": "python", "code": CODE}
    assert client.get(f"/practice/problems/{assessment}").status_code == 404
    for action in ("run", "submit"):
        url = f"/practice/problems/{assessment}/{action}"
        assert client.post(url, json=body, headers=headers()).status_code == 404
    assert sent == []


def test_problem_view_has_both_languages_and_no_hidden_data(client) -> None:
    res = client.get("/practice/problems/3sum")
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Three sum"
    assert set(body["languages"]) == {"python", "javascript"}
    py, js = body["languages"]["python"], body["languages"]["javascript"]
    assert py["file"] == "solution.py" and "def three_sum" in py["starter"]
    assert js["file"] == "solution.js" and "function three_sum" in js["starter"]
    assert py["parameters"] == ["nums"]
    assert len(py["examples"]) == 5
    assert not py["statement_md"].startswith("## Three sum")
    text = res.text
    assert "reference" not in text
    spec = practice.spec_for("3sum", "python")
    assert all(c.id.startswith("h") for c in spec.dsa_cases.hidden)
    assert not any(c.id in text for c in spec.dsa_cases.hidden)


def test_unknown_problem_is_404(client) -> None:
    assert client.get("/practice/problems/nope").status_code == 404
    body = {"language": "python", "code": CODE}
    assert (
        client.post("/practice/problems/nope/run", json=body, headers=headers()).status_code == 404
    )


def test_run_enqueues_a_visible_run(client, sent) -> None:
    res = client.post(
        "/practice/problems/3sum/run",
        json={"language": "python", "code": CODE},
        headers=headers(),
    )
    assert res.status_code == 200
    assert sent[0]["name"] == "practice_job"
    assert sent[0]["args"][2:] == ["run", "3sum", "python", CODE, None]
    view = client.get(f"/practice/jobs/{res.json()['job_id']}").json()
    assert view["status"] == "queued" and view["result"] is None


def test_custom_input_is_validated_before_queueing(client, sent) -> None:
    def post(custom: str):
        return client.post(
            "/practice/problems/3sum/run",
            json={"language": "python", "code": CODE, "custom_input": custom},
            headers=headers(),
        )

    assert post("not json").status_code == 422
    assert post('{"wrong": [1]}').status_code == 422
    assert post("[1, 2]").status_code == 422
    assert sent == []
    assert post('{"nums": [1, -1, 0]}').status_code == 200
    assert sent[0]["args"][-1] == {"nums": [1, -1, 0]}


def test_one_job_per_client_at_a_time(client, sent) -> None:
    body = {"language": "python", "code": CODE}
    assert (
        client.post("/practice/problems/3sum/submit", json=body, headers=headers()).status_code
        == 200
    )
    assert (
        client.post("/practice/problems/3sum/submit", json=body, headers=headers()).status_code
        == 409
    )
    practice_jobs.release(CLIENT, sent[0]["task_id"])
    assert (
        client.post("/practice/problems/3sum/submit", json=body, headers=headers()).status_code
        == 200
    )


def test_rate_limit(client, sent) -> None:
    body = {"language": "python", "code": CODE}
    for _ in range(practice_jobs.MAX_JOBS_PER_MINUTE):
        res = client.post("/practice/problems/3sum/run", json=body, headers=headers())
        assert res.status_code == 200
        practice_jobs.release(CLIENT, res.json()["job_id"])
    res = client.post("/practice/problems/3sum/run", json=body, headers=headers())
    assert res.status_code == 429


def test_client_id_is_required_and_checked(client, sent) -> None:
    body = {"language": "python", "code": CODE}
    assert client.post("/practice/problems/3sum/run", json=body).status_code == 422
    bad = client.post("/practice/problems/3sum/run", json=body, headers=headers("x"))
    assert bad.status_code == 422
    assert sent == []


def test_unknown_job_is_404(client) -> None:
    assert client.get(f"/practice/jobs/{uuid.uuid4()}").status_code == 404


def test_code_size_is_capped(client, sent) -> None:
    body = {"language": "python", "code": "x" * (practice.MAX_CODE_CHARS + 1)}
    assert (
        client.post("/practice/problems/3sum/run", json=body, headers=headers()).status_code == 422
    )


# --- Result shaping with a fake sandbox ------------------------------------------------


def program_run(cases: list[dict], status: str = "ok") -> ProgramRun:
    return ProgramRun(
        status=status,
        exit_code=0,
        report={"cases": cases},
        duration_ms=7,
        stdout_tail="printed",
        stderr_tail="",
    )


def test_custom_run_returns_output_without_an_expected_value(monkeypatch) -> None:
    seen = {}

    def fake(spec, files, cases, case_timeout_s=2.0):
        seen["cases"] = cases
        return program_run([{"id": "custom", "output": [[-1, 0, 1]], "duration_ms": 1}])

    monkeypatch.setattr(dsa, "execute_cases", fake)
    out = practice.run_custom("3sum", "python", CODE, {"nums": [-1, 0, 1]})
    assert out["output"] == "[[-1, 0, 1]]" and out["error"] is None and out["stdout"] == "printed"
    assert seen["cases"][0].expected is None


def test_custom_run_reports_a_candidate_error(monkeypatch) -> None:
    entry = {"id": "custom", "error": "ZeroDivisionError: division by zero", "duration_ms": 1}
    monkeypatch.setattr(dsa, "execute_cases", lambda *a, **k: program_run([entry]))
    out = practice.run_custom("3sum", "python", CODE, {"nums": [1]})
    assert out["output"] is None and "ZeroDivisionError" in out["error"]


def fake_results(passed_visible: int, passed_hidden: int, hidden_status: str = "ok"):
    from contracts_gen.run_result import RunResult, Summary

    def run_cases(spec, files, cases, expected_ids):
        is_hidden = cases[0].id.startswith("h")
        passed = passed_hidden if is_hidden else passed_visible
        status = hidden_status if is_hidden else "ok"
        return RunResult(
            status=status,
            reason=None,
            duration_ms=5,
            tests=[],
            summary=Summary(passed=passed, failed=len(cases) - passed, total=len(cases)),
            stdout_tail="",
            stderr_tail="",
        )

    return run_cases


def test_submit_accepts_when_every_case_passes(monkeypatch) -> None:
    monkeypatch.setattr(dsa, "run_cases", fake_results(5, 30))
    out = practice.submit("3sum", "python", CODE)
    assert out == {
        "kind": "submit",
        "status": "ok",
        "accepted": True,
        "passed": 35,
        "total": 35,
        "duration_ms": 10,
        "failed_stage": None,
    }


def test_submit_reports_counts_only_when_hidden_cases_fail(monkeypatch) -> None:
    monkeypatch.setattr(dsa, "run_cases", fake_results(5, 12))
    out = practice.submit("3sum", "python", CODE)
    assert out["accepted"] is False and (out["passed"], out["total"]) == (17, 35)
    assert out["failed_stage"] == "hidden"
    assert set(out) == {
        "kind",
        "status",
        "accepted",
        "passed",
        "total",
        "duration_ms",
        "failed_stage",
    }


def test_submit_stops_before_the_hidden_cases_when_an_example_fails(monkeypatch) -> None:
    ran = []
    inner = fake_results(3, 30)

    def run_cases(spec, files, cases, expected_ids):
        ran.append(cases[0].id)
        return inner(spec, files, cases, expected_ids)

    monkeypatch.setattr(dsa, "run_cases", run_cases)
    out = practice.submit("3sum", "python", CODE)
    assert out["accepted"] is False and out["failed_stage"] == "examples"
    assert (out["passed"], out["total"]) == (3, 35)
    assert all(not case_id.startswith("h") for case_id in ran)
    assert "stderr" not in out  # counts only, even for the visible stage


def test_submit_reports_a_hidden_timeout_as_status_only(monkeypatch) -> None:
    monkeypatch.setattr(dsa, "run_cases", fake_results(5, 0, hidden_status="timeout"))
    out = practice.submit("3sum", "python", CODE)
    assert out["status"] == "timeout" and out["accepted"] is False and out["passed"] == 5


def test_hidden_sample_is_stable_across_submits() -> None:
    spec = practice.spec_for("3sum", "python")
    a = dsa.hidden_sample(spec, practice.HIDDEN_SEED_KEY)
    b = dsa.hidden_sample(spec, practice.HIDDEN_SEED_KEY)
    assert a == b and len(a.case_ids) == 30
