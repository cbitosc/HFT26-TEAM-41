"""AI efficiency E for Adept/Master sessions (docs/BLUEPRINT.md section 5). Pure functions.

    PPH  = mean over hints: tests fixed within 5 min / tests failing at hint time
    TD   = share of hints preceded by >=1 run since the previous hint
    FREQ = 1 if 1-6 runs per 10 min, tapering to 0 outside
    IND  = 1 - min(1, (L1x1 + L2x2 + L3x3) / 12)
    E    = clamp(0.35 PPH + 0.20 TD + 0.15 FREQ + 0.30 IND - 0.15 extraction_attempts, 0, 1)
    E    = E x min(1, mean_correctness / 50)
    zero hints: E = mean_correctness / 100, minus 0.15 per extraction attempt (clamped)

Inputs are the session's stored runs and hint events, so a re-grade gives the same E.
"""

from dataclasses import dataclass

FIX_WINDOW_MS = 5 * 60_000
FREQ_LOW, FREQ_HIGH = 1.0, 6.0
"""Runs per 10 minutes that count as a healthy test rhythm."""
IND_SCALE = 12
EXTRACTION_PENALTY = 0.15
WEIGHTS = {"pph": 0.35, "td": 0.20, "freq": 0.15, "ind": 0.30}


@dataclass(frozen=True)
class HintRecord:
    ts: int
    task_id: str
    level: int
    blocked: bool
    """Replaced by a level-1 nudge: counts as level 1 for IND."""


@dataclass(frozen=True)
class RunRecord:
    ts: int
    task_id: str
    passing: frozenset[str]
    """Visible test ids that passed."""


@dataclass(frozen=True)
class Efficiency:
    value: float
    pph: float | None
    td: float | None
    freq: float | None
    ind: float | None
    extraction_attempts: int


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def pph(
    hints: list[HintRecord],
    runs: list[RunRecord],
    visible_ids: dict[str, list[str]],
    failing_at_start: dict[str, list[str]],
) -> float:
    """Mean share of the tests failing at hint time that pass in a run within 5 minutes.

    Failing at hint time: the visible tests the task's latest earlier run didn't pass, or
    `failing_at_start` before any run. A hint with nothing failing scores 0.
    """
    shares = []
    for hint in hints:
        task_runs = [r for r in runs if r.task_id == hint.task_id]
        before = [r for r in task_runs if r.ts <= hint.ts]
        if before:
            failing = set(visible_ids.get(hint.task_id, [])) - before[-1].passing
        else:
            failing = set(failing_at_start.get(hint.task_id, []))
        if not failing:
            shares.append(0.0)
            continue
        fixed: set[str] = set()
        for run in task_runs:
            if hint.ts < run.ts <= hint.ts + FIX_WINDOW_MS:
                fixed |= failing & run.passing
        shares.append(len(fixed) / len(failing))
    return sum(shares) / len(shares)


def td(hints: list[HintRecord], runs: list[RunRecord]) -> float:
    """Share of hints with a run on their task since that task's previous hint."""
    tried = 0
    previous: dict[str, int] = {}
    for hint in hints:
        since = previous.get(hint.task_id, -1)
        if any(r.task_id == hint.task_id and since < r.ts <= hint.ts for r in runs):
            tried += 1
        previous[hint.task_id] = hint.ts
    return tried / len(hints)


def freq(run_count: int, active_ms: int) -> float:
    """1 for 1-6 runs per 10 minutes; linear to 0 at 0 runs and at 12 per 10 minutes."""
    per_10_min = run_count / max(active_ms, 60_000) * 600_000
    if per_10_min < FREQ_LOW:
        return clamp(per_10_min / FREQ_LOW)
    if per_10_min > FREQ_HIGH:
        return clamp(1 - (per_10_min - FREQ_HIGH) / FREQ_HIGH)
    return 1.0


def ind(hints: list[HintRecord]) -> float:
    load = sum(1 if h.blocked else h.level for h in hints)
    return 1 - min(1.0, load / IND_SCALE)


def ai_efficiency(
    hints: list[HintRecord],
    runs: list[RunRecord],
    extraction_attempts: int,
    active_ms: int,
    mean_correctness: float,
    visible_ids: dict[str, list[str]],
    failing_at_start: dict[str, list[str]],
) -> Efficiency:
    """E in [0, 1]. `hints` and `runs` sorted by ts."""
    penalty = EXTRACTION_PENALTY * extraction_attempts
    if not hints:
        value = clamp(mean_correctness / 100 - penalty)
        return Efficiency(value, None, None, None, None, extraction_attempts)
    parts = {
        "pph": pph(hints, runs, visible_ids, failing_at_start),
        "td": td(hints, runs),
        "freq": freq(len(runs), active_ms),
        "ind": ind(hints),
    }
    raw = sum(WEIGHTS[k] * v for k, v in parts.items()) - penalty
    value = clamp(raw) * min(1.0, mean_correctness / 50)
    return Efficiency(value, **parts, extraction_attempts=extraction_attempts)
