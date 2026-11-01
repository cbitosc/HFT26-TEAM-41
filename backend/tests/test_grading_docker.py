"""Grading against real sandboxes, on the P1.3 demo task (builder.manual): the
py-fastapi-expenses seed with an off-by-one pagination bug. Run with `make test-docker`.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app import grading
from app.assessments import create_assessment
from app.models import AssessmentSession, Event, Run
from app.workspace import build_workspace, runnable_test_paths
from contracts_gen.task_spec import TaskSpec
from runner import run_tests
from tests.api_support import portfolio

pytestmark = pytest.mark.docker

FIX = "offset = (page - 1) * page_size"
BUG = "offset = (page - 2) * page_size"
FORCE_PASS = (
    "import pytest\n\n\n"
    "@pytest.hookimpl(hookwrapper=True)\n"
    "def pytest_runtest_makereport(item, call):\n"
    "    outcome = yield\n"
    "    outcome.get_result().outcome = 'passed'\n"
)


@pytest.fixture
def seed_spec(pagination_task) -> dict[str, Any]:
    return pagination_task.spec


@pytest.fixture
def session_id(db, seed_spec) -> str:
    assessment = create_assessment(db, portfolio(), "novice", [seed_spec])
    now = datetime.now(UTC)
    session = AssessmentSession(
        assessment_id=assessment.id, started_at=now, deadline_at=now + timedelta(minutes=60)
    )
    db.add(session)
    db.flush()
    return str(session.id)


def fixed_utils(spec: dict[str, Any]) -> dict[str, str]:
    return {"app/utils.py": spec["starter_files"]["app/utils.py"].replace(BUG, FIX)}


def test_real_run_stores_both_runs_and_one_event(db, seed_spec, session_id) -> None:
    visible = grading.process_run(db, session_id, "expenses-pagination", {})

    assert visible["status"] == "ok"
    assert 0 < visible["summary"]["failed"] < visible["summary"]["total"]
    runs = db.scalars(select(Run).order_by(Run.id)).all()
    assert [r.kind for r in runs] == ["visible", "silent"]
    [event] = db.scalars(select(Event)).all()
    assert event.payload["visible"]["total"] == len(seed_spec["visible_test_ids"])
    assert event.payload["hidden_silent"]["total"] == len(seed_spec["hidden_test_ids"])


def test_fix_passes_everything(db, seed_spec, session_id) -> None:
    grading.process_run(db, session_id, "expenses-pagination", fixed_utils(seed_spec))

    [event] = db.scalars(select(Event)).all()
    visible, hidden = event.payload["visible"], event.payload["hidden_silent"]
    assert visible["passed"] == visible["total"]
    assert hidden["passed"] == hidden["total"] and hidden["failing_ids"] == []


def test_candidate_conftest_forcing_passes_has_no_effect(db, seed_spec, session_id) -> None:
    spec = TaskSpec.model_validate(seed_spec)
    # Control: if it reached the sandbox, this conftest would turn every failure into a pass.
    tampered = build_workspace(spec, {}, spec.visible_tests) | {"tests/conftest.py": FORCE_PASS}
    paths = runnable_test_paths(spec.runtime, spec.visible_tests)
    control = run_tests(spec.runtime, tampered, paths)
    assert control.summary.passed == control.summary.total

    files = {"conftest.py": FORCE_PASS, "tests/conftest.py": FORCE_PASS}
    visible = grading.process_run(db, session_id, "expenses-pagination", files)

    assert visible["summary"]["failed"] > 0


def test_unexpected_test_set_is_an_error(db, seed_spec) -> None:
    ids = [*seed_spec["visible_test_ids"], "tests/test_pagination.py::test_ghost"]
    spec = TaskSpec.model_validate(seed_spec | {"visible_test_ids": ids})
    files = build_workspace(spec, fixed_utils(seed_spec), spec.visible_tests)

    result = grading.checked_run(spec.runtime, files, spec.visible_tests, spec.visible_test_ids)

    assert (result.status, result.reason, result.tests) == ("error", "test_set_mismatch", [])
