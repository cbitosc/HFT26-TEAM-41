"""The P1.3 demo tasks, built and validated in real sandboxes. Run with `make test-docker`."""

import pytest

from app import grading
from builder.manual import build_dsa_task, collect_test_names
from builder.seeds import SEEDS_DIR, seed_files
from contracts_gen.task_spec import TaskSpec

pytestmark = pytest.mark.docker

SEED_FILES = seed_files(SEEDS_DIR / "py-fastapi-expenses")
PAGINATION_NAMES = collect_test_names(SEED_FILES["tests/test_pagination.py"])


def function(test_id: str) -> str:
    return test_id.split("::", 1)[1].split("[", 1)[0]


def test_about_a_third_of_pagination_tests_are_visible(pagination_task) -> None:
    spec = pagination_task.spec
    visible = {function(i) for i in spec["visible_test_ids"]}

    assert all(i.startswith("tests/test_pagination.py::") for i in spec["visible_test_ids"])
    assert len(visible) == round(len(PAGINATION_NAMES) / 3)
    hidden_pagination = {
        function(i)
        for i in spec["hidden_test_ids"]
        if i.startswith("tests/test_pagination_hidden.py::")
    }
    assert visible | hidden_pagination == set(PAGINATION_NAMES)
    assert not visible & hidden_pagination


def test_all_other_seed_tests_are_hidden(pagination_task) -> None:
    other = {p for p in SEED_FILES if p.startswith("tests/test_") and "pagination" not in p}
    hidden_files = {i.split("::")[0] for i in pagination_task.spec["hidden_test_ids"]}

    assert hidden_files == other | {"tests/test_pagination_hidden.py"}


def test_visible_and_hidden_tests_both_catch_the_bug(pagination_task) -> None:
    spec = TaskSpec.model_validate(pagination_task.spec)
    starter = grading.grade_task(spec, {})

    assert set(spec.visible_test_ids) - starter.visible_passed  # a visible test fails
    hidden_failing = set(spec.hidden_test_ids) - starter.hidden_passed
    assert any(i.startswith("tests/test_pagination_hidden.py::") for i in hidden_failing)


def test_pagination_task_validation_and_certificate(pagination_task) -> None:
    validation = pagination_task.validation
    certificate = pagination_task.spec["certificate"]

    assert validation["starter_fails_visible"] and validation["reference_passes_all"]
    assert (certificate["reference_pass"], certificate["starter_fail"]) == (True, True)
    assert certificate["scope_files"] == ["app/utils.py"]


def test_dsa_task_validation() -> None:
    built = build_dsa_task()

    assert built.validation["starter_fails_visible"]
    assert built.validation["reference_passes_all"]
    assert built.validation["reference"] == {"visible": "5/5", "hidden": "30/30"}
    assert built.spec["certificate"]["reference_pass"] is True
