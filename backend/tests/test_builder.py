"""Builder pieces that need no Docker: the AST bug, the test split, the visible-test rule."""

import ast

import pytest

from builder.manual import (
    choose_visible,
    collect_test_names,
    dsa_task_spec,
    inject_offset_bug,
    split_test_module,
)
from builder.seeds import SEEDS_DIR, seed_files
from contracts_gen.task_spec import TaskSpec

FILES = seed_files(SEEDS_DIR / "py-fastapi-expenses")
UTILS = FILES["app/utils.py"]
PAGINATION = FILES["tests/test_pagination.py"]


def test_offset_bug_changes_exactly_one_line() -> None:
    buggy = inject_offset_bug(UTILS)

    changed = [
        (old, new)
        for old, new in zip(UTILS.splitlines(), buggy.splitlines(), strict=True)
        if old != new
    ]
    assert changed == [
        ("    offset = (page - 1) * page_size", "    offset = (page - 2) * page_size")
    ]
    ast.parse(buggy)


def test_offset_bug_is_deterministic_and_refuses_a_second_application() -> None:
    assert inject_offset_bug(UTILS) == inject_offset_bug(UTILS)
    with pytest.raises(ValueError, match="found 0"):
        inject_offset_bug(inject_offset_bug(UTILS))


def test_split_partitions_tests_and_keeps_the_header() -> None:
    names = collect_test_names(PAGINATION)
    selected = {names[0], names[3]}

    visible, hidden = split_test_module(PAGINATION, selected)

    assert collect_test_names(visible) == [names[0], names[3]]
    assert collect_test_names(hidden) == [n for n in names if n not in selected]
    for module in (visible, hidden):
        ast.parse(module)
        assert "def twenty_five(add_expense):" in module  # fixture kept
        assert "def get_page(" in module  # helper kept
        assert module.startswith("import pytest\n")
    # Decorators travel with their test.
    assert "@pytest.mark.parametrize" in hidden


def test_split_rejects_unknown_tests() -> None:
    with pytest.raises(ValueError, match="unknown"):
        split_test_module(PAGINATION, {"test_nope"})


def test_choose_visible_takes_a_third_with_one_failing_test() -> None:
    names = [f"test_{c}" for c in "abcdefgh"]  # 8 tests -> 3 visible

    visible = choose_visible(names, failing={"test_c", "test_f"})

    assert visible == ["test_a", "test_b", "test_c"]  # source order, first failing included


def test_choose_visible_needs_a_failing_test() -> None:
    with pytest.raises(ValueError, match="fail"):
        choose_visible(["test_a", "test_b"], failing=set())


def test_dsa_spec_is_valid_and_its_ids_are_the_case_ids() -> None:
    spec = TaskSpec.model_validate(dsa_task_spec())

    assert spec.visible_test_ids == [c.id for c in spec.dsa_cases.visible]
    assert spec.hidden_test_ids == [c.id for c in spec.dsa_cases.hidden]
    assert (len(spec.visible_test_ids), len(spec.hidden_test_ids)) == (5, 30)
    assert spec.dsa_cases.comparator is None
    assert list(spec.starter_files) == ["solution.py"]
