"""Mutation pre-filter and draft task in real sandboxes. Run with `make test-docker`."""

import pytest

from builder.manual import EXPENSES_SEED
from builder.mutate import MAX_RUNS, draft_novice_task, inject_bug, prefilter, ranked
from builder.tasks import load_seed

pytestmark = pytest.mark.docker

RNG_SEED = 0


@pytest.fixture(scope="module")
def checked():
    return prefilter(EXPENSES_SEED, "pagination", inject_bug(EXPENSES_SEED, "pagination", RNG_SEED))


def test_at_least_three_valid_candidates_for_pagination(checked) -> None:
    _, concepts = load_seed(EXPENSES_SEED)
    pagination_tests = set(concepts["concepts"]["pagination"]["tests"])
    kept = ranked(checked)

    assert len(checked) <= MAX_RUNS
    assert len(kept) >= 3
    for c in kept:
        assert 1 <= c.failing <= 0.4 * c.total
        assert c.failing_tests & pagination_tests


def test_rejected_candidates_say_why(checked) -> None:
    rejected = [c for c in checked if not c.kept]

    assert all(c.reason != "kept" for c in rejected)
    assert all(c.failing == 0 or c.failing > 0.4 * c.total for c in rejected if c.total)


def test_preferred_candidates_come_first(checked) -> None:
    order = [1 <= c.failing <= 5 for c in ranked(checked)]

    assert order == sorted(order, reverse=True)


def test_draft_task_is_a_validated_novice_spec(checked) -> None:
    best = ranked(checked)[0]

    built = draft_novice_task(EXPENSES_SEED, "pagination", best, RNG_SEED)
    spec, validation = built.spec, built.validation

    assert (spec["tier"], spec["mode"], spec["kind"]) == ("novice", "seed", "domain")
    assert spec["target_symbols"] == best.candidate.target_symbols
    assert spec["statement_md"].startswith("TODO(P2.5)")
    assert spec["certificate"]["scope_files"] == [best.candidate.file]
    assert validation["starter_fails_visible"] and validation["reference_passes_all"]
    # About a third of the pagination tests are visible, all from the pagination module.
    visible_functions = {i.split("[")[0] for i in spec["visible_test_ids"]}
    assert all(i.startswith("tests/test_pagination.py::") for i in visible_functions)
    assert len(visible_functions) == round(8 / 3)
