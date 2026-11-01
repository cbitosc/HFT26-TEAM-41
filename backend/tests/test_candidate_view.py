"""to_candidate_view must never let backend-only TaskSpec data through (CLAUDE.md rule 2)."""

import pytest

from app.candidate_view import to_candidate_view
from contracts_gen.candidate_task_view import CandidateTaskView
from contracts_gen.task_spec import TaskSpec
from tests.api_support import LEAK_MARKER, LEAK_SEED, domain_spec, dsa_spec, leaky

BACKEND_ONLY = {
    "reference_ref",
    "target_symbols",
    "hidden_tests",
    "certificate",
    "random_seeds",
    "mode",
    "seed_id",
    "ai_solve_rate",
    "difficulty_index",
}


@pytest.mark.parametrize("spec", [domain_spec(), dsa_spec()], ids=["domain", "dsa"])
def test_view_has_no_backend_only_data(spec: dict) -> None:
    view = to_candidate_view(TaskSpec.model_validate(leaky(spec)))
    dumped = view.model_dump(mode="json")
    text = view.model_dump_json()

    assert set(dumped) == set(CandidateTaskView.model_fields)
    assert not BACKEND_ONLY & set(dumped)
    assert LEAK_MARKER not in text
    assert str(LEAK_SEED) not in text


def test_view_keeps_visible_parts() -> None:
    spec = TaskSpec.model_validate(dsa_spec())
    view = to_candidate_view(spec)

    assert view.starter_files == spec.starter_files
    assert [c.id for c in view.dsa_cases.visible] == [c.id for c in spec.dsa_cases.visible]
    assert set(view.dsa_cases.model_dump()) == {"visible"}


def test_perf_keeps_budget_but_not_input_generator() -> None:
    spec = TaskSpec.model_validate(domain_spec())
    view = to_candidate_view(spec)

    assert view.perf.model_dump() == {"budget_ms": spec.perf.budget_ms}
