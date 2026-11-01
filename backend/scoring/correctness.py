"""Per-task correctness, final score and band (BLUEPRINT §5). Pure functions."""

from contracts_gen.run_result import RunResult

VISIBLE_WEIGHT = 0.3
HIDDEN_WEIGHT = 0.7
PERF_FLOOR = 0.5
PERF_FLOOR_AT = 3.0
"""perf_factor falls linearly from 1.0 at the budget to PERF_FLOOR at PERF_FLOOR_AT × budget."""

BANDS = [(80.0, "strong"), (60.0, "pass"), (45.0, "borderline")]


def passed_ids(result: RunResult, expected_ids: list[str]) -> set[str]:
    """Expected tests that passed. A run that isn't "ok" passes nothing."""
    if result.status != "ok":
        return set()
    return {t.id for t in result.tests if t.outcome == "passed"} & set(expected_ids)


def rate(passed: int, total: int) -> float | None:
    """Share of tests passed; None when there are no tests."""
    if total == 0:
        return None
    return passed / total


def perf_factor(budget_ms: int | None, perf_ms: float | None) -> float:
    """1.0 without a perf constraint or within budget. A task with a budget but no
    measurement (the perf test crashed before recording a time) gets PERF_FLOOR."""
    if budget_ms is None:
        return 1.0
    if perf_ms is None:
        return PERF_FLOOR
    if perf_ms <= budget_ms:
        return 1.0
    over = (perf_ms - budget_ms) / ((PERF_FLOOR_AT - 1) * budget_ms)
    return max(PERF_FLOOR, 1.0 - (1.0 - PERF_FLOOR) * over)


def regression_factor(still_passing: int, pass_to_pass: int) -> float:
    """Share of the tests that passed on the starter (pass_to_pass) that still pass.
    1.0 when there are none."""
    return 1.0 if pass_to_pass == 0 else still_passing / pass_to_pass


def correctness(
    visible_rate: float | None,
    hidden_rate: float | None,
    factor: float,
    regression: float = 1.0,
) -> float:
    """100 × (0.3 × visible_rate + 0.7 × hidden_rate) × regression_factor × perf_factor.

    The rates are fail_to_pass rates (share of the tests failing on the starter that now
    pass) when the task records them, else shares of all tests. A missing rate (no tests of
    that kind) gives its weight to the other one; a task with no tests at all scores 0.
    """
    if visible_rate is None and hidden_rate is None:
        return 0.0
    if visible_rate is None:
        combined = hidden_rate
    elif hidden_rate is None:
        combined = visible_rate
    else:
        combined = VISIBLE_WEIGHT * visible_rate + HIDDEN_WEIGHT * hidden_rate
    return 100.0 * combined * regression * factor


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def final_score(tier: str, mean_correctness: float, ai_efficiency: float | None) -> float:
    """Novice: mean correctness. Adept/Master: 0.8 × mean correctness + 20 × E."""
    if tier == "novice":
        return mean_correctness
    if ai_efficiency is None:
        raise ValueError(f"tier {tier} needs an AI efficiency")
    return 0.8 * mean_correctness + 20.0 * ai_efficiency


def band(score: float) -> str:
    for threshold, name in BANDS:
        if score >= threshold:
            return name
    return "not_yet"
