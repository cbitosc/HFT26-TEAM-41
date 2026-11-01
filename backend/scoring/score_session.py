"""Score a submitted session from stored records only: submit runs, events, task specs.

No LLM and no sandbox: the same records always give the same breakdown, so a re-grade
reproduces the score exactly. Floats are rounded so the stored JSON is stable.
"""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import dsa
from app.models import Assessment, AssessmentSession, Event, Run, Task
from contracts_gen.event import HiddenSample
from contracts_gen.run_result import RunResult
from contracts_gen.score_breakdown import ScoreBreakdown, TaskScore, TestCounts
from contracts_gen.task_spec import TaskSpec
from scoring import correctness as c
from scoring import efficiency as eff

# 2: fail_to_pass rates and regression_factor (P2.7b). 3: AI efficiency from hints (F2).
SCORING_VERSION = "3"

logger = logging.getLogger(__name__)


def score_session(db: Session, session_id: uuid.UUID) -> ScoreBreakdown:
    session = db.get(AssessmentSession, session_id)
    if session is None:
        raise ValueError(f"session {session_id} not found")
    tier = db.get(Assessment, session.assessment_id).tier
    tasks = db.scalars(
        select(Task).where(Task.assessment_id == session.assessment_id).order_by(Task.order)
    ).all()
    first_focus = _per_task(db, session_id, "focus", func.min(Event.ts))
    last_edit = _per_task(db, session_id, "edit", func.max(Event.ts))
    run_counts = _per_task(db, session_id, "run", func.count(Event.id))

    specs = [TaskSpec.model_validate(task.spec) for task in tasks]
    scores = [
        _task_score(
            spec,
            str(session_id),
            _latest_submit(db, session_id, spec.task_id),
            first_focus.get(spec.task_id),
            last_edit.get(spec.task_id),
            run_counts.get(spec.task_id, 0),
        )
        for spec in specs
    ]
    mean_correctness = c.mean([s.correctness for s in scores])
    efficiency = None
    if tier != "novice":
        efficiency = ai_efficiency(db, session, specs, mean_correctness).value
    final = round(c.final_score(tier, mean_correctness, efficiency), 2)
    return ScoreBreakdown(
        scoring_version=SCORING_VERSION,
        tier=tier,
        final_score=final,
        band=c.band(final),
        mean_correctness=round(mean_correctness, 2),
        ai_efficiency=None if efficiency is None else round(efficiency, 4),
        tasks=scores,
    )


def _task_score(
    spec: TaskSpec,
    session_id: str,
    submit: Run | None,
    first_focus: int | None,
    last_edit: int | None,
    runs: int,
) -> TaskScore:
    """Counts come from the submit run; a task without one (never graded) passes nothing.

    DSA hidden cases are the sample stored on the submit run (never re-sampled), or the
    session's sample when there is no submit run.
    """
    visible_passed: set[str] = set()
    hidden_passed: set[str] = set()
    perf_ms = None
    sample = dsa.hidden_sample(spec, session_id)
    if submit is not None and "hidden_sample" in submit.result:
        sample = HiddenSample.model_validate(submit.result["hidden_sample"])
    hidden_expected = sample.case_ids if sample is not None else spec.hidden_test_ids
    if submit is not None:
        visible = RunResult.model_validate(submit.result["visible"])
        hidden = RunResult.model_validate(submit.result["hidden"])
        visible_passed = c.passed_ids(visible, spec.visible_test_ids)
        hidden_passed = c.passed_ids(hidden, hidden_expected)
        # Measured by the submit job for tasks with a perf budget (grading.measure_perf).
        perf_ms = submit.result.get("perf_ms")

    # Domain tasks with gate-recorded ids: SWE-bench style, only the tests the starter
    # fails count, and pass_to_pass tests broken by the candidate cost points. DSA tasks:
    # every case is something to solve (all of them count as fail_to_pass).
    f2p, p2p = spec.fail_to_pass, spec.pass_to_pass
    by_f2p = spec.kind == "domain" and f2p is not None and p2p is not None
    if spec.kind == "domain" and not by_f2p:
        logger.info("task %s has no fail_to_pass ids: scoring all tests", spec.task_id)
    visible_f2p = hidden_f2p = still_passing = None
    regression = 1.0
    if by_f2p:
        visible_f2p = TestCounts(
            passed=len(visible_passed & set(f2p.visible)), total=len(f2p.visible)
        )
        hidden_f2p = TestCounts(passed=len(hidden_passed & set(f2p.hidden)), total=len(f2p.hidden))
        p2p_ids = set(p2p.visible) | set(p2p.hidden)
        still_passing = TestCounts(
            passed=len((visible_passed | hidden_passed) & p2p_ids), total=len(p2p_ids)
        )
        regression = c.regression_factor(still_passing.passed, still_passing.total)
        visible_rate = c.rate(visible_f2p.passed, visible_f2p.total)
        hidden_rate = c.rate(hidden_f2p.passed, hidden_f2p.total)
    else:
        visible_rate = c.rate(len(visible_passed), len(spec.visible_test_ids))
        hidden_rate = c.rate(len(hidden_passed), len(hidden_expected))
    budget_ms = spec.perf.budget_ms if spec.perf else None
    factor = c.perf_factor(budget_ms, perf_ms)
    time_ms = None
    if first_focus is not None and last_edit is not None:
        time_ms = max(0, last_edit - first_focus)
    return TaskScore(
        task_id=spec.task_id,
        kind=spec.kind,
        visible=TestCounts(passed=len(visible_passed), total=len(spec.visible_test_ids)),
        hidden=TestCounts(passed=len(hidden_passed), total=len(hidden_expected)),
        visible_rate=_round(visible_rate, 4),
        hidden_rate=_round(hidden_rate, 4),
        perf_budget_ms=budget_ms,
        perf_ms=perf_ms,
        perf_factor=round(factor, 4),
        correctness=round(c.correctness(visible_rate, hidden_rate, factor, regression), 2),
        time_ms=time_ms,
        runs=runs,
        rates_over="fail_to_pass" if by_f2p else "all_tests",
        visible_f2p=visible_f2p,
        hidden_f2p=hidden_f2p,
        pass_to_pass=still_passing,
        regression_factor=round(regression, 4),
        mutation_score=_mutation_score(spec),
    )


def _mutation_score(spec: TaskSpec) -> float | None:
    """Shown on the report, never scored. Certificates from before the gate hold a 0.0
    placeholder (their reference_pass is a boolean), which means "not measured"."""
    certificate = spec.certificate
    return None if isinstance(certificate.reference_pass, bool) else certificate.mutation_score


def ai_efficiency(
    db: Session, session: AssessmentSession, specs: list[TaskSpec], mean_correctness: float
) -> eff.Efficiency:
    """E (BLUEPRINT section 5) from the stored hint events and visible runs."""
    events = db.scalars(
        select(Event)
        .where(Event.session_id == session.id, Event.type.in_(("hint_request", "hint_response")))
        .order_by(Event.ts, Event.id)
    ).all()
    hints = [
        eff.HintRecord(e.ts, e.task_id, e.payload["level"], e.payload["blocked"])
        for e in events
        if e.type == "hint_response"
    ]
    attempts = sum(e.type == "hint_request" and e.payload["flagged_extraction"] for e in events)
    visible_ids = {spec.task_id: spec.visible_test_ids for spec in specs}
    runs = [
        eff.RunRecord(
            _ms(run.ts),
            run.task_id,
            frozenset(
                c.passed_ids(RunResult.model_validate(run.result), visible_ids.get(run.task_id, []))
            ),
        )
        for run in db.scalars(
            select(Run)
            .where(Run.session_id == session.id, Run.kind == "visible")
            .order_by(Run.ts, Run.id)
        )
    ]
    failing_at_start = {
        spec.task_id: spec.fail_to_pass.visible if spec.fail_to_pass else spec.visible_test_ids
        for spec in specs
    }
    end = session.submitted_at or session.deadline_at
    return eff.ai_efficiency(
        hints,
        runs,
        attempts,
        _ms(end) - _ms(session.started_at),
        mean_correctness,
        visible_ids,
        failing_at_start,
    )


def _ms(moment) -> int:
    return int(moment.timestamp() * 1000)


def _latest_submit(db: Session, session_id: uuid.UUID, task_id: str) -> Run | None:
    return db.scalars(
        select(Run)
        .where(Run.session_id == session_id, Run.task_id == task_id, Run.kind == "submit")
        .order_by(Run.ts.desc(), Run.id.desc())
        .limit(1)
    ).first()


def _per_task(db: Session, session_id: uuid.UUID, event_type: str, aggregate) -> dict:
    rows = db.execute(
        select(Event.task_id, aggregate)
        .where(Event.session_id == session_id, Event.type == event_type)
        .group_by(Event.task_id)
    )
    return {task_id: value for task_id, value in rows}


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)
