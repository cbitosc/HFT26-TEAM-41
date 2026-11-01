"""AI efficiency E (BLUEPRINT section 5, F2): pure formulas, then scoring a session."""

import pytest

from scoring import efficiency as eff
from scoring.score_session import score_session
from tests.test_hints import MINUTE, T0, add_run
from tests.test_scores_api import (
    HIDDEN_IDS,
    TASK,
    VISIBLE_IDS,
    add_event,
    add_submit_run,
    result,
    start_session,
)

A, B = VISIBLE_IDS
IDS = {TASK: VISIBLE_IDS}


def hint(ts: int, level: int = 1, blocked: bool = False) -> eff.HintRecord:
    return eff.HintRecord(ts, TASK, level, blocked)


def run(ts: int, *passing: str) -> eff.RunRecord:
    return eff.RunRecord(ts, TASK, frozenset(passing))


def test_pph_counts_tests_fixed_within_five_minutes() -> None:
    runs = [run(0), run(2 * MINUTE, A), run(9 * MINUTE, A, B)]
    # At the hint both tests fail; A is fixed within 5 min, B only after 9.
    assert eff.pph([hint(MINUTE)], runs, IDS, IDS) == 0.5
    # Before any run, the failing set is the task's starting one.
    assert eff.pph([hint(-MINUTE)], [run(MINUTE, A)], IDS, {TASK: [A]}) == 1.0
    # Nothing failing at hint time: the hint helped nothing.
    assert eff.pph([hint(3 * MINUTE)], [run(MINUTE, A, B)], IDS, IDS) == 0.0


def test_td_needs_a_run_on_the_task_since_the_previous_hint() -> None:
    hints = [hint(MINUTE), hint(2 * MINUTE), hint(4 * MINUTE)]
    runs = [run(30_000), run(3 * MINUTE)]

    assert eff.td(hints, runs) == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    ("runs", "minutes", "expected"),
    [(0, 60, 0.0), (3, 60, 0.5), (6, 60, 1.0), (36, 60, 1.0), (54, 60, 0.5), (90, 60, 0.0)],
)
def test_freq_tapers_outside_one_to_six_runs_per_ten_minutes(runs, minutes, expected) -> None:
    assert eff.freq(runs, minutes * MINUTE) == pytest.approx(expected)


def test_ind_weights_levels_and_counts_a_nudge_as_level_one() -> None:
    assert eff.ind([hint(0, 1), hint(1, 2)]) == pytest.approx(0.75)
    assert eff.ind([hint(0, 3, blocked=True)]) == pytest.approx(1 - 1 / 12)
    assert eff.ind([hint(i, 3) for i in range(5)]) == 0.0


def test_zero_hints_use_mean_correctness_minus_extraction_attempts() -> None:
    assert eff.ai_efficiency([], [], 0, MINUTE, 80, IDS, IDS).value == 0.8
    assert eff.ai_efficiency([], [], 2, MINUTE, 80, IDS, IDS).value == pytest.approx(0.5)
    assert eff.ai_efficiency([], [], 9, MINUTE, 80, IDS, IDS).value == 0.0


def test_e_combines_the_parts_and_scales_with_correctness() -> None:
    hints = [hint(MINUTE, 1)]
    runs = [run(30_000), run(2 * MINUTE, A, B)] + [run(i * MINUTE) for i in range(3, 6)]
    full = eff.ai_efficiency(hints, runs, 0, 10 * MINUTE, 100, IDS, IDS)
    # PPH 1, TD 1, FREQ 1 (5 runs / 10 min), IND 11/12.
    assert (full.pph, full.td, full.freq) == (1.0, 1.0, 1.0)
    assert full.value == pytest.approx(0.35 + 0.20 + 0.15 + 0.30 * 11 / 12)
    half = eff.ai_efficiency(hints, runs, 0, 10 * MINUTE, 25, IDS, IDS)
    assert half.value == pytest.approx(full.value / 2)
    caught = eff.ai_efficiency(hints, runs, 1, 10 * MINUTE, 100, IDS, IDS)
    assert caught.value == pytest.approx(full.value - 0.15)


def test_a_session_with_hints_scores_and_rescores_identically(db) -> None:
    session_id = start_session(db, tier="adept")
    add_run(db, session_id, T0, [])
    add_event(
        db, session_id, "hint_request", T0 + 1000, {"level_allowed": 1, "flagged_extraction": False}
    )
    add_event(
        db,
        session_id,
        "hint_response",
        T0 + 2000,
        {"level": 1, "mentions": ["add"], "similarity": 0.0, "blocked": False},
    )
    add_event(
        db,
        session_id,
        "hint_request",
        T0 + MINUTE,
        {"level_allowed": 1, "flagged_extraction": True},
    )
    add_run(db, session_id, T0 + 2 * MINUTE, VISIBLE_IDS)
    add_submit_run(db, session_id, result(VISIBLE_IDS, []), result(HIDDEN_IDS, []))

    first = score_session(db, session_id)
    second = score_session(db, session_id)

    assert first.model_dump_json() == second.model_dump_json()
    assert first.scoring_version == "3"
    assert 0 < first.ai_efficiency < 1
    # Full correctness, PPH 1 and TD 1, one extraction attempt.
    assert first.final_score == pytest.approx(80 + 20 * first.ai_efficiency, abs=0.01)
