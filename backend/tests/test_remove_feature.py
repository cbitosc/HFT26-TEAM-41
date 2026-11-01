"""Feature removal: eligibility, stubbing, concept dependencies (no Docker)."""

import ast

import libcst as cst
import pytest

from builder.manual import EXPENSES_SEED
from builder.remove_feature import (
    FeatureRemovalError,
    concept_spans,
    concept_targets,
    dependent_concepts,
    eligible,
    remove_feature,
    stub_module,
    stubbed_starter,
    suggest_seed_changes,
)
from builder.tasks import load_seed, starter_base

FILES, CONCEPTS = load_seed(EXPENSES_SEED)

SNIPPET = '''\
import functools


class Cache:
    """A cache."""

    def __init__(self) -> None:
        self.items = {}

    @property
    def size(self) -> int:
        """How many entries are stored.

        More detail here.
        """
        return len(self.items)


@functools.cache
def total(values: list[int], start: int = 0) -> int:
    """Sum of "values" plus start."""
    # a comment inside the body
    return start + sum(values)


def undocumented(x: int) -> int:
    return x
'''


def test_eligible_concepts_span_two_or_three_files() -> None:
    spans = concept_spans(FILES, CONCEPTS)

    assert eligible(spans) == ["auth", "importing", "reporting"]
    assert spans["reporting"] == ["app/routes.py", "app/services.py", "app/utils.py"]
    assert spans["pagination"] == ["app/utils.py"]


def test_ineligible_concept_error_lists_the_eligible_ones() -> None:
    with pytest.raises(
        FeatureRemovalError, match="Eligible concepts in .*: auth, importing, reporting"
    ):
        remove_feature(EXPENSES_SEED, "pagination")


def test_targets_are_functions_and_methods_not_data_classes() -> None:
    reporting = concept_targets(FILES, CONCEPTS["concepts"]["reporting"]["symbols"])
    caching = concept_targets(FILES, CONCEPTS["concepts"]["caching"]["symbols"])

    assert reporting == [
        "app/services.py::compute_monthly_report",
        "app/utils.py::month_bounds",
        "app/routes.py::get_monthly_report",
    ]  # MonthlyReport (a data class) stays as the interface
    assert "app/services.py::ReportCache.get" in caching
    assert "app/services.py::ReportCache.__init__" not in caching


def test_stub_keeps_signature_decorators_and_docstring() -> None:
    stubbed = stub_module(SNIPPET, ["total", "Cache.size"])

    tree = ast.parse(stubbed)
    total = next(n for n in tree.body if getattr(n, "name", "") == "total")
    assert ast.get_docstring(total) == 'Sum of "values" plus start.'
    assert [ast.unparse(d) for d in total.decorator_list] == ["functools.cache"]
    assert ast.unparse(total.args) == "values: list[int], start: int=0"
    assert "raise NotImplementedError('TODO: Sum of \"values\" plus start.')" in ast.unparse(total)
    assert "# a comment inside the body" not in stubbed
    assert 'raise NotImplementedError("TODO: How many entries are stored.")' in stubbed
    assert "self.items = {}" in stubbed  # __init__ untouched
    assert "def undocumented(x: int) -> int:\n    return x\n" in stubbed


def test_stub_refuses_a_target_without_docstring() -> None:
    with pytest.raises(FeatureRemovalError, match="undocumented has no docstring"):
        stub_module(SNIPPET, ["undocumented"])


def test_starter_differs_only_in_the_target_files() -> None:
    targets = concept_targets(FILES, CONCEPTS["concepts"]["reporting"]["symbols"])

    starter = stubbed_starter(FILES, targets)

    base = starter_base(FILES)
    assert sorted(p for p in base if starter[p] != base[p]) == [
        "app/routes.py",
        "app/services.py",
        "app/utils.py",
    ]
    for path in ("app/routes.py", "app/services.py", "app/utils.py"):
        cst.parse_module(starter[path])
        assert starter[path].count("raise NotImplementedError") == 1


def test_concepts_that_call_the_removed_code_are_dependents() -> None:
    reporting = concept_targets(FILES, CONCEPTS["concepts"]["reporting"]["symbols"])
    auth = concept_targets(FILES, CONCEPTS["concepts"]["auth"]["symbols"])

    assert dependent_concepts(FILES, CONCEPTS, "reporting", reporting) == ["caching", "importing"]
    assert dependent_concepts(FILES, CONCEPTS, "auth", auth) == []


def test_suggestions_when_no_concept_is_eligible() -> None:
    spans = {"alone": ["app/a.py"], "wide": ["a.py", "b.py", "c.py", "d.py"], "empty": []}

    suggestions = suggest_seed_changes(spans)

    assert eligible(spans) == []
    assert any(s.startswith("alone: all its code is in app/a.py; move") for s in suggestions)
    assert any(s.startswith("wide: spans 4 files; narrow") for s in suggestions)
    assert any(s.startswith("empty: list at least two functions") for s in suggestions)
