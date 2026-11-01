"""Hidden DSA cases sampled per session (P2.6): stable per session, stored on submit, and
re-grades reproduce the score byte for byte. The sandbox is faked (no Docker)."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import dsa, grading
from app.assessments import create_assessment
from app.models import AssessmentSession, Event, FileSnapshot, Run
from builder import dsa_bank
from contracts_gen.task_spec import TaskSpec
from runner import ProgramRun
from tests.api_support import portfolio

PROBLEM = next(p for p in dsa_bank.load_bank() if len(dsa_bank.load_cases(p)["hidden"]) > 40)
SPEC = dsa_bank.task_spec(
    PROBLEM, "Story.", dsa_bank.identity_names(PROBLEM), "python311", PROBLEM.tiers[0]
)
TASK = SPEC["task_id"]
GOOD = "# solves the even-numbered cases\n"


@pytest.fixture
def sandbox(monkeypatch) -> list[list[str]]:
    """Fake harness: right answers for even case numbers when solution.py is GOOD."""
    seen: list[list[str]] = []

    def execute(spec, candidate_files, cases, case_timeout_s=dsa.CASE_TIMEOUT_S):
        seen.append([c.id for c in cases])
        good = candidate_files.get("solution.py") == GOOD
        entries = [
            {
                "id": c.id,
                "output": c.expected if good and int(c.id[1:]) % 2 == 0 else "wrong",
                "duration_ms": 1,
            }
            for c in cases
        ]
        return ProgramRun(
            status="ok",
            exit_code=0,
            report={"cases": entries},
            duration_ms=5,
            stdout_tail="",
            stderr_tail="",
        )

    monkeypatch.setattr(dsa, "execute_cases", execute)
    return seen


def start_session(db) -> uuid.UUID:
    assessment = create_assessment(db, portfolio(), "novice", [SPEC])
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


def test_sample_is_stable_per_session_and_differs_across_sessions() -> None:
    spec = TaskSpec.model_validate(SPEC)
    first = dsa.hidden_sample(spec, "session-a")
    assert first == dsa.hidden_sample(spec, "session-a")
    assert len(first.case_ids) == dsa.HIDDEN_SAMPLE_SIZE
    assert set(first.case_ids) <= set(spec.hidden_test_ids)
    assert first.case_ids != dsa.hidden_sample(spec, "session-b").case_ids
    pool = spec.hidden_test_ids
    assert first.case_ids == [i for i in pool if i in set(first.case_ids)]  # pool order


def test_a_domain_task_has_no_sample() -> None:
    from tests.grading_support import tiny_spec

    assert dsa.hidden_sample(TaskSpec.model_validate(tiny_spec()), "s") is None


def test_regrade_after_a_sampled_submit_is_byte_identical(db, http, sandbox) -> None:
    session_id = start_session(db)
    expected = dsa.hidden_sample(TaskSpec.model_validate(SPEC), str(session_id))
    grading.process_run(db, str(session_id), TASK, {"solution.py": GOOD})
    db.add(
        FileSnapshot(
            session_id=session_id, task_id=TASK, ts=datetime.now(UTC), files={"solution.py": GOOD}
        )
    )
    db.flush()
    grading.process_submit(db, str(session_id))

    # Visible, hidden (run); visible, hidden (submit): hidden runs got only the sample.
    assert sandbox[1] == sandbox[3] == expected.case_ids
    submit = db.scalars(select(Run).where(Run.session_id == session_id, Run.kind == "submit")).one()
    assert submit.result["hidden_sample"] == expected.model_dump(mode="json")
    event = db.scalars(
        select(Event).where(Event.session_id == session_id, Event.type == "submit")
    ).one()
    assert event.payload["hidden_sample"] == expected.model_dump(mode="json")
    assert event.payload["hidden"]["total"] == dsa.HIDDEN_SAMPLE_SIZE

    stored = http.get(f"/sessions/{session_id}/score").json()["breakdown"]
    first = http.post(f"/sessions/{session_id}/regrade")
    second = http.post(f"/sessions/{session_id}/regrade")
    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert json.loads(first.content) == stored
    hidden = stored["tasks"][0]["hidden"]
    assert hidden["total"] == dsa.HIDDEN_SAMPLE_SIZE
    assert hidden["passed"] == sum(int(i[1:]) % 2 == 0 for i in expected.case_ids)
    assert len(sandbox) == 4  # re-grades never run code


def test_regrade_uses_the_stored_sample_not_a_fresh_one(db, http, sandbox, monkeypatch) -> None:
    session_id = start_session(db)
    db.add(
        FileSnapshot(
            session_id=session_id, task_id=TASK, ts=datetime.now(UTC), files={"solution.py": GOOD}
        )
    )
    db.flush()
    grading.process_submit(db, str(session_id))
    before = http.post(f"/sessions/{session_id}/regrade").content
    # Even if the sampling rule changed later, the stored ids decide.
    monkeypatch.setattr(dsa, "HIDDEN_SAMPLE_SIZE", 5)
    assert http.post(f"/sessions/{session_id}/regrade").content == before
