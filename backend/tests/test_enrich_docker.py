"""Entity renaming checked in real sandboxes (LLM not involved). Run with `make test-docker`."""

import pytest

from builder import enrich as e
from builder.manual import build_pagination_task

pytestmark = pytest.mark.docker

RENAMES = {"expense": "order", "category": "department"}


@pytest.fixture(scope="module")
def task() -> dict:
    # The demo task is never enriched, but it is a small validated seed task to rename.
    return build_pagination_task().spec


def test_renaming_keeps_all_test_results_identical(task) -> None:
    renamed, status = e.sandbox_rename_check(task, e.renamed_spec(task, RENAMES), RENAMES)

    assert status == "applied"
    assert renamed["visible_test_ids"] == [
        e.rename_text(i, RENAMES) for i in task["visible_test_ids"]
    ]
    assert len(renamed["hidden_test_ids"]) == len(task["hidden_test_ids"])
    assert "class Order(Base)" in renamed["starter_files"]["app/models.py"]


def test_renaming_that_changes_a_result_is_dropped(task) -> None:
    broken = e.renamed_spec(task, RENAMES)
    # A rename that misses one use breaks the app: the check must notice and refuse it.
    models = broken["starter_files"]["app/models.py"]
    broken["starter_files"]["app/models.py"] = models.replace(
        '__tablename__ = "orders"', '__tablename__ = "expenses"'
    ).replace("class Order(Base)", "class Expense(Base)")

    renamed, status = e.sandbox_rename_check(task, broken, RENAMES)

    assert renamed is None
    assert status.startswith("dropped")
