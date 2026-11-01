"""Mutation operators and candidate enumeration (no Docker)."""

import ast

import pytest

from builder.manual import EXPENSES_SEED, demo_starter_utils, inject_offset_bug
from builder.mutate import inject_bug, mutations
from builder.seeds import SEEDS_DIR, seed_files
from builder.tasks import load_seed, starter_base

SNIPPET = '''\
"""A module with comments that must survive."""

LIMIT = 10  # module constant


def clamp(value: int, low: int, high: int) -> int:
    # Keep value within [low, high].
    if low > high:
        raise ValueError("bad range")
    return max(low, min(value, high))


def window(items: list, start: int, size: int) -> list:
    end = start + size - 1
    return items[start:end + 1]


def is_member(name: str, names: list, strict: bool) -> bool:
    return name in names and strict


def scale(x: int, factor: int) -> int:
    return x * factor


def describe(count: int) -> str:
    if count == 0:
        return "none"
    return "some"


def report(page: int, size, total: int) -> dict:
    return dict(page=page, size=size, total=total)
'''


def changes(qualname: str, operator: str) -> list[str]:
    """The changed lines of every `operator` mutation of `qualname` in SNIPPET."""
    result = []
    for mutation in mutations(SNIPPET, qualname, [operator]):
        before, after = SNIPPET.splitlines(), mutation.source.splitlines()
        assert len(after) <= len(before)
        result.append(" | ".join(line.strip() for line in after if line not in before))
    return result


def test_comparison_flip() -> None:
    assert changes("clamp", "comparison_flip") == ["if low >= high:"]
    assert changes("describe", "comparison_flip") == ["if count != 0:"]
    assert changes("is_member", "comparison_flip") == ["return name not in names and strict"]


def test_off_by_one_on_constants_and_index_arithmetic() -> None:
    assert changes("window", "off_by_one") == [
        "end = start + size",  # dropped `- 1`
        "end = start + size - 2",
        "return items[start:end]",  # dropped `+ 1`
        "return items[start:end + 2]",
    ]
    assert changes("describe", "off_by_one") == ["if count == -1:", "if count == 1:"]


def test_boolean_operator_swap() -> None:
    assert changes("is_member", "boolean_swap") == ["return name in names or strict"]


def test_removed_guard() -> None:
    [mutation] = mutations(SNIPPET, "clamp", ["removed_guard"])

    assert "if low > high" not in mutation.source
    assert "raise ValueError" not in mutation.source
    assert "return max(low, min(value, high))" in mutation.source


def test_removed_guard_keeps_a_valid_block_when_the_guard_is_alone() -> None:
    source = "def f(x: int) -> None:\n    if x < 0:\n        return\n"

    [mutation] = mutations(source, "f", ["removed_guard"])

    assert mutation.source == "def f(x: int) -> None:\n    pass\n"


def test_swapped_arguments_needs_the_same_known_type() -> None:
    # clamp: `min(value, high)` -> both int; `max(low, min(...))` -> min(...) has no known type
    assert changes("clamp", "swapped_arguments") == ["return max(low, min(high, value))"]
    # report: `size` has no annotation, so only page/total... which are not adjacent
    assert changes("report", "swapped_arguments") == []


def test_wrong_return() -> None:
    assert changes("is_member", "wrong_return") == ["return not (name in names and strict)"]
    assert changes("scale", "wrong_return") == ["return None"]


def test_mutations_keep_the_rest_of_the_file_byte_for_byte() -> None:
    for mutation in mutations(SNIPPET, "clamp"):
        before, after = SNIPPET.splitlines(), mutation.source.splitlines()
        if len(before) == len(after):
            assert sum(a != b for a, b in zip(before, after, strict=True)) == 1
        assert '"""A module with comments that must survive."""' in mutation.source
        assert "# Keep value within [low, high]." in mutation.source
        assert "LIMIT = 10  # module constant" in mutation.source


def test_unknown_symbol_is_an_error() -> None:
    with pytest.raises(ValueError, match="not found"):
        mutations(SNIPPET, "missing")


def test_same_rng_seed_gives_identical_candidates() -> None:
    first = inject_bug(EXPENSES_SEED, "pagination", 7)
    again = inject_bug(EXPENSES_SEED, "pagination", 7)
    other = inject_bug(EXPENSES_SEED, "pagination", 8)

    assert first == again
    assert [c.diff for c in first] != [c.diff for c in other]
    assert sorted(c.diff for c in first) == sorted(c.diff for c in other)  # same sites


def test_each_candidate_changes_one_file_inside_a_concept_symbol() -> None:
    files, concepts = load_seed(EXPENSES_SEED)
    base = starter_base(files)
    symbols = concepts["concepts"]["pagination"]["symbols"]

    candidates = inject_bug(EXPENSES_SEED, "pagination", 0)

    assert len(candidates) >= 10
    for c in candidates:
        changed = [p for p in base if c.starter_files[p] != base[p]]
        assert changed == [c.file]
        assert set(c.starter_files) == set(base)
        ast.parse(c.starter_files[c.file])
        assert any(c.target_symbols[0].startswith(s) for s in symbols)
        assert c.diff.startswith(f"--- a/{c.file}\n+++ b/{c.file}\n")
        assert c.line > 0 and c.changed_line


def test_unknown_concept_lists_the_known_ones() -> None:
    with pytest.raises(ValueError, match="pagination"):
        inject_bug(EXPENSES_SEED, "telepathy", 0)


def test_demo_bug_comes_from_the_engine_and_matches_the_hand_bug() -> None:
    reference = seed_files(SEEDS_DIR / EXPENSES_SEED)["app/utils.py"]

    assert demo_starter_utils(reference) == inject_offset_bug(reference)
