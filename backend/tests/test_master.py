"""Master builder (P2.4) without sandboxes: perf operators, calibration, perf parsing, scoring."""

import ast
from datetime import UTC, datetime

import pytest

from app.models import Run
from builder import perf
from builder.manual import EXPENSES_SEED
from builder.master import (
    PERF_OPERATORS,
    Calibration,
    MasterError,
    PerfCandidate,
    SiteCheck,
    budget_for,
    build_master,
    calibrate,
    perf_candidates,
)
from builder.mutate import mutations
from builder.tasks import load_seed, starter_base
from contracts_gen.task_spec import TaskSpec
from runner.sandbox import ProgramRun
from scoring.score_session import _task_score
from tests.grading_support import tiny_spec


def regress(source: str, qualname: str, operator: str) -> list[str]:
    found = mutations(source, qualname, [operator], table=PERF_OPERATORS)
    for mutation in found:
        ast.parse(mutation.source)  # every regression is valid Python
    return [mutation.source for mutation in found]


def run_both(before: str, after: str, call: str) -> tuple[object, object]:
    results = []
    for source in (before, after):
        scope: dict = {}
        exec(source, scope)  # snippets defined in this file
        results.append(eval(call, scope))
    return results[0], results[1]


# --- Operators: each changes complexity, never the result ----------------------------

SET_LOOKUP = """
def new_ids(stored, incoming):
    seen = set(stored)
    return [i for i in incoming if i not in seen]
"""


def test_list_scan_turns_a_membership_set_into_a_list() -> None:
    [after] = regress(SET_LOOKUP, "new_ids", "list_scan")

    assert "seen = list(stored)" in after
    assert run_both(SET_LOOKUP, after, "new_ids([1, 2, 3], [2, 4, 4])") == ([4, 4], [4, 4])


DICT_GET = """
def prices(rows, wanted):
    by_id = {row[0]: row[1] for row in rows}
    return [by_id.get(w, 0) for w in wanted]
"""


def test_list_scan_turns_dict_get_into_a_linear_search() -> None:
    [after] = regress(DICT_GET, "prices", "list_scan")

    assert "next((value for key, value in by_id.items() if key == w), 0)" in after
    before_result, after_result = run_both(DICT_GET, after, "prices([(1, 5), (2, 7)], [2, 9])")
    assert before_result == after_result == [7, 0]


CACHE_LOOKUP = """
CALLS = []

def compute(key):
    CALLS.append(key)
    return key * 2

def cached(cache, key):
    value = cache.get(key)
    if value is None:
        value = compute(key)
        cache[key] = value
    return value

def twice(key):
    cache = {}
    return [cached(cache, key), cached(cache, key), len(CALLS)]
"""


def test_cache_bypass_keeps_the_lookup_but_always_recomputes() -> None:
    [after] = regress(CACHE_LOOKUP, "cached", "cache_bypass")

    assert "value = cache.get(key)\n    value = compute(key)" in after
    assert "if value is None" not in after
    assert run_both(CACHE_LOOKUP, after, "twice(3)") == ([6, 6, 1], [6, 6, 2])


LRU = """
import functools

@functools.lru_cache(maxsize=None)
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)
"""


def test_cache_bypass_removes_an_lru_cache_decorator() -> None:
    [after] = regress(LRU, "fib", "cache_bypass")

    assert "lru_cache" not in after
    assert run_both(LRU, after, "fib(15)") == (610, 610)


BATCHED = """
class Session:
    def __init__(self):
        self.queries = 0

    def execute(self, keys):
        self.queries += 1
        return [k * 10 for k in keys]


class Col:
    def in_(self, keys):
        return list(keys)

    def __eq__(self, key):
        return [key]


def load(session, col, ids):
    rows = session.execute(col.in_(ids))
    return sorted(rows)


def run(ids):
    session = Session()
    return load(session, Col(), ids), session.queries
"""


def test_n_plus_one_runs_one_query_per_key() -> None:
    [after] = regress(BATCHED, "load", "n_plus_one")

    assert "[match for id in ids for match in session.execute(col == id)]" in after
    assert run_both(BATCHED, after, "run([1, 2, 3])") == (([10, 20, 30], 1), ([10, 20, 30], 3))


DEDUP = """
def unique(items):
    keys = list(dict.fromkeys(item.lower() for item in items))
    return keys
"""


def test_quadratic_dedup_keeps_order_with_a_linear_check_per_item() -> None:
    [after] = regress(DEDUP, "unique", "quadratic_dedup")

    assert "keys = []\n    for value in (item.lower() for item in items):" in after
    assert "if value not in keys:" in after
    before_result, after_result = run_both(DEDUP, after, "unique(['b', 'A', 'a', 'B', 'c'])")
    assert before_result == after_result == ["b", "a", "c"]


def test_every_operator_finds_a_site_in_the_expenses_seed() -> None:
    found = {c.operator for c in perf_candidates(EXPENSES_SEED, 0)}

    assert found == set(PERF_OPERATORS)


def test_perf_candidates_are_deterministic_per_rng_seed() -> None:
    first = [(c.operator, c.line) for c in perf_candidates(EXPENSES_SEED, 3)]

    assert first == [(c.operator, c.line) for c in perf_candidates(EXPENSES_SEED, 3)]


def test_perf_files_are_never_in_a_starter() -> None:
    files, _ = load_seed(EXPENSES_SEED)

    assert any(path.startswith(perf.PERF_DIR) for path in files)
    assert not any(path.startswith(perf.PERF_DIR) for path in starter_base(files))


# --- Calibration ----------------------------------------------------------------------


def candidate(operator: str, test: str = "tests/perf/test_x.py::test_x") -> PerfCandidate:
    return PerfCandidate(
        operator,
        "app/services.py",
        1,
        operator,
        "app/services.py::f",
        test,
        "tests/perf/gen.py",
        "",
        "",
    )


def test_budget_is_three_times_the_median_rounded_up() -> None:
    assert budget_for([10.0, 12.0, 11.0, 50.0, 9.0]) == 33
    assert budget_for([6.1, 6.2, 6.3]) == 19


def test_calibration_rejects_a_regression_within_budget_and_tries_the_next() -> None:
    measured = {"slow_enough": 200.0, "too_fast": 25.0}
    reference_calls = []

    def reference_runs(test: str) -> list[float]:
        reference_calls.append(test)
        return [10.0, 10.0, 11.0, 9.0, 10.0]

    result = calibrate(
        [candidate("too_fast"), candidate("slow_enough")],
        reference_runs,
        lambda c: SiteCheck([], measured[c.operator]),
    )

    assert [(t.candidate.operator, t.kept) for t in result.tried] == [
        ("too_fast", False),
        ("slow_enough", True),
    ]
    assert result.tried[0].reason == "within budget (25.0 <= 30 ms)"
    assert (result.chosen.operator, result.budget_ms, result.ref_ms, result.naive_ms) == (
        "slow_enough",
        30,
        10.0,
        200.0,
    )
    assert reference_calls == ["tests/perf/test_x.py::test_x"]  # measured once per perf test


def test_calibration_rejects_a_regression_that_breaks_functional_tests() -> None:
    result = calibrate(
        [candidate("breaks")],
        lambda test: [10.0] * 5,
        lambda c: SiteCheck(["tests/test_cache.py::test_hit"], 900.0),
    )

    assert result.chosen is None
    assert result.tried[0].reason == "breaks 1 functional tests"


def test_build_master_fails_when_no_regression_exceeds_the_budget() -> None:
    with pytest.raises(MasterError, match="no perf regression exceeds its budget"):
        build_master(
            EXPENSES_SEED, ["pagination"], 0, lambda test: [100.0] * 5, lambda c: SiteCheck([], 1.0)
        )


def test_empty_calibration_has_no_choice() -> None:
    assert calibrate([], lambda test: [], lambda c: SiteCheck([], None)) == Calibration()


# --- Reading perf_ms from the sandbox report ------------------------------------------


def fake_program(monkeypatch, status: str, report: dict | None) -> None:
    run = ProgramRun(status, 0 if report else None, report, 5, "", "")
    monkeypatch.setattr(perf, "run_program", lambda *args, **kwargs: run)


def test_perf_ms_comes_from_record_property(monkeypatch) -> None:
    report = {
        "exitcode": 0,
        "tests": [
            {
                "nodeid": "tests/perf/test_p.py::test_p",
                "outcome": "passed",
                "user_properties": [{"perf_ms": 42.5}],
            },
            {"nodeid": "tests/test_a.py::test_a", "outcome": "passed"},
        ],
    }
    fake_program(monkeypatch, "ok", report)

    run = perf.run_with_perf("python311", {}, ["tests"], 60)

    assert (run.status, run.perf_ms, len(run.tests)) == ("ok", 42.5, 2)


def test_timeout_counts_as_the_time_limit(monkeypatch) -> None:
    fake_program(monkeypatch, "timeout", None)

    assert perf.run_with_perf("python311", {}, ["tests"], 60).perf_ms == 60_000.0


@pytest.mark.parametrize("bad", ["fast", -1, float("nan"), None])
def test_invalid_perf_values_are_ignored(monkeypatch, bad) -> None:
    report = {
        "tests": [{"nodeid": "t", "outcome": "passed", "user_properties": [{"perf_ms": bad}]}]
    }
    fake_program(monkeypatch, "ok", report)

    assert perf.run_with_perf("python311", {}, ["tests"], 60).perf_ms is None


# --- Scoring uses the measured perf_ms ------------------------------------------------


def perf_task_score(perf_ms: float | None):
    spec = TaskSpec.model_validate(
        tiny_spec() | {"perf": {"budget_ms": 100, "input_gen": "tests/perf/gen_large.py"}}
    )
    passed = spec.visible_test_ids + spec.hidden_test_ids

    def result(ids: list[str]) -> dict:
        tests = [
            {"id": i, "name": i, "outcome": "passed", "duration_ms": 1, "message": None}
            for i in ids
        ]
        return {
            "status": "ok",
            "reason": None,
            "duration_ms": 1,
            "tests": tests,
            "summary": {"passed": len(ids), "failed": 0, "total": len(ids)},
            "stdout_tail": "",
            "stderr_tail": "",
        }

    submit = Run(
        kind="submit",
        result={
            "visible": result([i for i in passed if i in spec.visible_test_ids]),
            "hidden": result([i for i in passed if i in spec.hidden_test_ids]),
            "perf_ms": perf_ms,
        },
        ts=datetime.now(UTC),
    )
    return _task_score(spec, "session-1", submit, None, None, 1)


@pytest.mark.parametrize(
    ("perf_ms", "factor", "correctness"),
    [(80.0, 1.0, 100.0), (200.0, 0.75, 75.0), (900.0, 0.5, 50.0), (None, 0.5, 50.0)],
)
def test_perf_factor_uses_the_measured_perf_ms(perf_ms, factor, correctness) -> None:
    score = perf_task_score(perf_ms)

    assert (score.perf_budget_ms, score.perf_ms) == (100, perf_ms)
    assert (score.perf_factor, score.correctness) == (factor, correctness)
