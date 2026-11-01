"""Pure scoring formulas (BLUEPRINT §5)."""

import pytest

from scoring import correctness as c


def test_rate_of_no_tests_is_none() -> None:
    assert c.rate(0, 0) is None
    assert c.rate(3, 4) == 0.75


@pytest.mark.parametrize(
    ("visible", "hidden", "expected"),
    [
        (1.0, 1.0, 100.0),  # all pass
        (0.0, 0.0, 0.0),  # all fail
        (1.0, 0.0, 30.0),
        (0.0, 1.0, 70.0),
        (2 / 3, 0.5, 55.0),
    ],
)
def test_correctness_weights_visible_30_hidden_70(visible, hidden, expected) -> None:
    assert c.correctness(visible, hidden, 1.0) == pytest.approx(expected)


def test_missing_rate_gives_its_weight_to_the_other() -> None:
    assert c.correctness(None, 0.5, 1.0) == pytest.approx(50.0)
    assert c.correctness(0.5, None, 1.0) == pytest.approx(50.0)


def test_zero_tests_scores_zero() -> None:
    assert c.correctness(None, None, 1.0) == 0.0


def test_perf_factor_scales_correctness() -> None:
    assert c.correctness(1.0, 1.0, 0.5) == pytest.approx(50.0)


@pytest.mark.parametrize(
    ("budget", "measured", "expected"),
    [
        (None, 500.0, 1.0),  # no perf constraint
        (None, None, 1.0),
        (100, None, 0.5),  # budget but nothing measured: fails closed
        (100, 50.0, 1.0),
        (100, 100.0, 1.0),  # exactly at budget
        (100, 200.0, 0.75),  # 2× budget: halfway to the floor
        (100, 300.0, 0.5),  # 3× budget
        (100, 10_000.0, 0.5),  # beyond 3×
    ],
)
def test_perf_factor(budget, measured, expected) -> None:
    assert c.perf_factor(budget, measured) == pytest.approx(expected)


def test_final_score_by_tier() -> None:
    assert c.final_score("novice", 72.5, None) == 72.5
    assert c.final_score("adept", 50.0, 0.5) == pytest.approx(50.0)
    with pytest.raises(ValueError):
        c.final_score("master", 50.0, None)


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (100.0, "strong"),
        (80.0, "strong"),
        (79.99, "pass"),
        (60.0, "pass"),
        (45.0, "borderline"),
        (44.99, "not_yet"),
        (0.0, "not_yet"),
    ],
)
def test_bands(score, band) -> None:
    assert c.band(score) == band


def test_mean_of_nothing_is_zero() -> None:
    assert c.mean([]) == 0.0


def test_regression_factor_is_the_share_of_pass_to_pass_still_passing() -> None:
    assert c.regression_factor(3, 4) == 0.75
    assert c.regression_factor(0, 0) == 1.0  # nothing passed on the starter


def test_regression_factor_scales_correctness() -> None:
    assert c.correctness(1.0, 1.0, 1.0, regression=0.75) == 75.0
    assert c.correctness(1.0, 1.0, 0.5, regression=0.5) == 25.0
