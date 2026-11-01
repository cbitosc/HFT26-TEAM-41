"""Session scoring from stored records, the score endpoint and re-grade determinism."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import grading
from app.assessments import create_assessment
from app.models import AssessmentSession, Event, FileSnapshot, Run, Score
from scoring.score_session import score_session
from tests.api_support import LEAK_MARKER, dsa_spec, portfolio
from tests.grading_support import FIXED, FakeRunner, tiny_spec

TASK = "tiny-add"
VISIBLE_IDS = tiny_spec()["visible_test_ids"]
HIDDEN_IDS = tiny_spec()["hidden_test_ids"]


@pytest.fixture
def runner(monkeypatch) -> FakeRunner:
    fake = FakeRunner()
    monkeypatch.setattr(grading, "run_tests", fake)
    return fake


def start_session(db: Session, tier: str = "novice", spec: dict | None = None) -> uuid.UUID:
    assessment = create_assessment(db, portfolio(), tier, [spec or tiny_spec()])
    now = datetime.now(UTC)
    session = AssessmentSession(
        assessment_id=assessment.id,
        started_at=now,
        deadline_at=now + timedelta(minutes=60),
        status="active",
    )
    db.add(session)
    db.flush()
    return session.id


def add_event(db: Session, session_id: uuid.UUID, type_: str, ts: int, payload: dict) -> None:
    db.add(Event(session_id=session_id, task_id=TASK, ts=ts, type=type_, payload=payload))


def submit_fixed(db: Session, session_id: uuid.UUID) -> None:
    db.add(
        FileSnapshot(
            session_id=session_id, task_id=TASK, ts=datetime.now(UTC), files={"app/calc.py": FIXED}
        )
    )
    db.flush()
    grading.process_submit(db, str(session_id))


def result(passed: list[str], failed: list[str]) -> dict:
    tests = [
        {"id": i, "name": i, "outcome": o, "duration_ms": 1, "message": None}
        for ids, o in ((passed, "passed"), (failed, "failed"))
        for i in ids
    ]
    summary = {"passed": len(passed), "failed": len(failed), "total": len(tests)}
    return {
        "status": "ok",
        "reason": None,
        "duration_ms": 1,
        "tests": tests,
        "summary": summary,
        "stdout_tail": "",
        "stderr_tail": "",
    }


def add_submit_run(db: Session, session_id: uuid.UUID, visible: dict, hidden: dict) -> None:
    db.add(
        Run(
            session_id=session_id,
            task_id=TASK,
            kind="submit",
            result={"visible": visible, "hidden": hidden},
            ts=datetime.now(UTC),
        )
    )
    db.flush()


# --- score_session ---


def test_full_marks_with_time_and_run_count(db, runner) -> None:
    session_id = start_session(db)
    add_event(db, session_id, "focus", 1_000, {"file": "app/calc.py", "line": 1, "symbol": None})
    add_event(db, session_id, "edit", 3_000, {"file": "app/calc.py", "symbol": None,
                                              "chars_added": 1, "chars_removed": 1})  # fmt: skip
    add_event(db, session_id, "focus", 5_000, {"file": "app/calc.py", "line": 2, "symbol": None})
    add_event(db, session_id, "edit", 9_000, {"file": "app/calc.py", "symbol": None,
                                              "chars_added": 2, "chars_removed": 0})  # fmt: skip
    grading.process_run(db, str(session_id), TASK, {"app/calc.py": FIXED})
    grading.process_run(db, str(session_id), TASK, {"app/calc.py": FIXED})

    submit_fixed(db, session_id)

    [score] = db.scalars(select(Score).where(Score.session_id == session_id)).all()
    assert score.breakdown == {
        "scoring_version": "3",
        "tier": "novice",
        "final_score": 100.0,
        "band": "strong",
        "mean_correctness": 100.0,
        "ai_efficiency": None,
        "tasks": [
            {
                "task_id": TASK,
                "kind": "domain",
                "visible": {"passed": 2, "total": 2},
                "hidden": {"passed": 1, "total": 1},
                "visible_rate": 1.0,
                "hidden_rate": 1.0,
                "perf_budget_ms": None,
                "perf_ms": None,
                "perf_factor": 1.0,
                "correctness": 100.0,
                "time_ms": 8_000,  # first focus to last edit
                "runs": 2,
                "rates_over": "all_tests",  # tiny_spec has no fail_to_pass ids
                "visible_f2p": None,
                "hidden_f2p": None,
                "pass_to_pass": None,
                "regression_factor": 1.0,
                "mutation_score": 0.86,  # from the fixture's certificate, not scored
            }
        ],
    }


def test_partial_submission(db) -> None:
    session_id = start_session(db)
    add_submit_run(db, session_id, result(VISIBLE_IDS[:1], VISIBLE_IDS[1:]), result([], HIDDEN_IDS))

    breakdown = score_session(db, session_id)

    [task] = breakdown.tasks
    assert (task.visible.passed, task.hidden.passed) == (1, 0)
    assert task.correctness == 15.0  # 100 × 0.3 × 1/2
    assert task.time_ms is None and task.runs == 0
    assert (breakdown.final_score, breakdown.band) == (15.0, "not_yet")


def test_unexpected_test_ids_do_not_count(db) -> None:
    session_id = start_session(db)
    smuggled = result([*VISIBLE_IDS, "tests/test_visible.py::test_extra"], [])
    add_submit_run(db, session_id, smuggled, result(HIDDEN_IDS, []))

    [task] = score_session(db, session_id).tasks

    assert task.visible.passed == 2
    assert task.hidden.passed == 1


def test_task_without_submit_run_scores_zero(db) -> None:
    [task] = score_session(db, start_session(db)).tasks

    assert task.correctness == 0.0
    assert task.visible.model_dump() == {"passed": 0, "total": 2}


def test_adept_without_hints_uses_mean_correctness_as_efficiency(db) -> None:
    session_id = start_session(db, tier="adept")
    add_submit_run(db, session_id, result(VISIBLE_IDS[:1], VISIBLE_IDS[1:]), result([], HIDDEN_IDS))

    breakdown = score_session(db, session_id)

    assert breakdown.ai_efficiency == 0.15
    assert breakdown.final_score == 15.0  # 0.8 × 15 + 20 × 0.15


# --- fail_to_pass scoring (P2.7b) ---

F2P_VISIBLE, P2P_VISIBLE = "tests/test_visible.py::test_adds", "tests/test_visible.py::test_zero"
F2P_HIDDEN = "tests/test_hidden.py::test_fixed"
P2P_HIDDEN = [f"tests/test_hidden.py::test_works_{i}" for i in range(3)]


def f2p_spec() -> dict:
    """A gate-certified task: 1 visible + 1 hidden test fail on the starter, 4 already pass."""
    return tiny_spec() | {
        "visible_test_ids": [F2P_VISIBLE, P2P_VISIBLE],
        "hidden_test_ids": [F2P_HIDDEN, *P2P_HIDDEN],
        "fail_to_pass": {"visible": [F2P_VISIBLE], "hidden": [F2P_HIDDEN]},
        "pass_to_pass": {"visible": [P2P_VISIBLE], "hidden": P2P_HIDDEN},
    }


def f2p_score(db, visible_passed, visible_failed, hidden_passed, hidden_failed):
    session_id = start_session(db, spec=f2p_spec())
    add_submit_run(
        db,
        session_id,
        result(visible_passed, visible_failed),
        result(hidden_passed, hidden_failed),
    )
    return session_id, score_session(db, session_id)


def test_an_untouched_starter_scores_zero(db) -> None:
    _, breakdown = f2p_score(db, [P2P_VISIBLE], [F2P_VISIBLE], P2P_HIDDEN, [F2P_HIDDEN])

    [task] = breakdown.tasks
    assert task.rates_over == "fail_to_pass"
    assert (task.visible_f2p.passed, task.hidden_f2p.passed) == (0, 0)
    assert task.regression_factor == 1.0
    assert task.correctness == 0.0  # the old formula gave 100 × (0.3 × 1/2 + 0.7 × 3/4) = 67.5
    assert breakdown.final_score == 0.0


def test_a_full_fix_scores_100(db) -> None:
    _, breakdown = f2p_score(db, [F2P_VISIBLE, P2P_VISIBLE], [], [F2P_HIDDEN, *P2P_HIDDEN], [])

    [task] = breakdown.tasks
    assert (task.visible_rate, task.hidden_rate, task.regression_factor) == (1.0, 1.0, 1.0)
    assert task.pass_to_pass.model_dump() == {"passed": 4, "total": 4}
    assert task.correctness == 100.0


def test_a_fix_that_breaks_a_passing_test_loses_points(db) -> None:
    hidden = [F2P_HIDDEN, *P2P_HIDDEN[1:]]
    _, breakdown = f2p_score(db, [F2P_VISIBLE, P2P_VISIBLE], [], hidden, P2P_HIDDEN[:1])

    [task] = breakdown.tasks
    assert task.pass_to_pass.model_dump() == {"passed": 3, "total": 4}
    assert task.regression_factor == 0.75
    assert task.correctness == 75.0


def test_a_partial_fix_counts_only_fail_to_pass_tests(db) -> None:
    passed = [F2P_HIDDEN, *P2P_HIDDEN]
    _, breakdown = f2p_score(db, [P2P_VISIBLE], [F2P_VISIBLE], passed, [])

    [task] = breakdown.tasks
    assert (task.visible_rate, task.hidden_rate) == (0.0, 1.0)
    assert task.correctness == 70.0


def test_dsa_scoring_is_unchanged_every_case_counts(db) -> None:
    spec = dsa_spec()  # gate-certified: carries fail_to_pass and pass_to_pass
    session_id = start_session(db, spec=spec)
    visible, hidden = spec["visible_test_ids"], spec["hidden_test_ids"]
    db.add(
        Run(
            session_id=session_id,
            task_id=spec["task_id"],
            kind="submit",
            result={"visible": result(visible[:2], visible[2:]), "hidden": result(hidden, [])},
            ts=datetime.now(UTC),
        )
    )
    db.flush()

    [task] = score_session(db, session_id).tasks

    assert task.rates_over == "all_tests"
    assert task.visible_rate == round(2 / len(visible), 4) and task.hidden_rate == 1.0
    assert task.correctness == round(100 * (0.3 * 2 / len(visible) + 0.7), 2)


def test_tasks_without_fail_to_pass_ids_use_all_tests_and_log_it(db, caplog) -> None:
    session_id = start_session(db)
    add_submit_run(db, session_id, result(VISIBLE_IDS[:1], VISIBLE_IDS[1:]), result([], HIDDEN_IDS))

    with caplog.at_level("INFO", logger="scoring.score_session"):
        [task] = score_session(db, session_id).tasks

    assert task.rates_over == "all_tests" and task.correctness == 15.0
    assert "has no fail_to_pass ids" in caplog.text


def test_f2p_rescoring_is_byte_identical(db) -> None:
    session_id, first = f2p_score(db, [F2P_VISIBLE], [P2P_VISIBLE], P2P_HIDDEN, [F2P_HIDDEN])

    assert score_session(db, session_id).model_dump_json() == first.model_dump_json()


# --- API ---


def test_score_status_follows_the_session(db, http, runner) -> None:
    session_id = start_session(db)
    assert http.get(f"/sessions/{session_id}/score").json()["status"] == "in_progress"

    db.get(AssessmentSession, session_id).status = "submitted"
    db.flush()
    assert http.get(f"/sessions/{session_id}/score").json() == {
        "status": "grading",
        "computed_at": None,
        "breakdown": None,
    }

    submit_fixed(db, session_id)
    body = http.get(f"/sessions/{session_id}/score").json()
    assert body["status"] == "graded"
    assert body["breakdown"]["final_score"] == 100.0


def test_score_of_unknown_session_is_404(http) -> None:
    assert http.get(f"/sessions/{uuid.uuid4()}/score").status_code == 404
    assert http.post(f"/sessions/{uuid.uuid4()}/regrade").status_code == 404


def test_regrade_before_grading_is_409(db, http) -> None:
    assert http.post(f"/sessions/{start_session(db)}/regrade").status_code == 409


def test_two_regrades_give_byte_identical_json(db, http, runner) -> None:
    session_id = start_session(db)
    add_event(db, session_id, "focus", 1_000, {"file": "app/calc.py", "line": 1, "symbol": None})
    grading.process_run(db, str(session_id), TASK, {"app/calc.py": FIXED})
    submit_fixed(db, session_id)

    first = http.post(f"/sessions/{session_id}/regrade")
    second = http.post(f"/sessions/{session_id}/regrade")

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    stored = db.scalars(select(Score).where(Score.session_id == session_id)).all()
    assert len(stored) == 3  # submit + two regrades
    assert json.loads(first.content) == stored[0].breakdown
    assert http.get(f"/sessions/{session_id}/score").json()["breakdown"] == stored[0].breakdown


def test_score_response_has_no_hidden_data(db, http, runner) -> None:
    session_id = start_session(db)
    submit_fixed(db, session_id)

    for response in (
        http.get(f"/sessions/{session_id}/score"),
        http.post(f"/sessions/{session_id}/regrade"),
    ):
        assert response.status_code == 200
        assert LEAK_MARKER not in response.text
