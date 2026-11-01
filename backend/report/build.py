"""Assemble the report details of a graded session from stored records (no LLM, no sandbox).

certificates   the validation gate's certificate per task
claims         report.claims.claim_map
timeline       per task: visible and hidden pass rates at each run and at submit, with
               hint markers (hidden counts come from the silent runs, never test ids)
integrity      pastes (large ones, and ones within PASTE_AFTER_HINT_MS of a hint), tab
               blurs, suspicious-code flags and refused writes to protected files
efficiency     the AI efficiency parts and weights (Adept/Master), as scored
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assessment, AssessmentSession, Event, Run, Score, Task
from contracts_gen.profile import Profile
from contracts_gen.task_spec import TaskSpec
from gate import rules_profile
from report.claims import Claim, claim_map
from scoring import efficiency as eff
from scoring.score_session import ai_efficiency

LARGE_PASTE_CHARS = 300
PASTE_AFTER_HINT_MS = 2 * 60_000


@dataclass(frozen=True)
class Point:
    ts: int
    minute: float
    """Minutes since the session started."""
    kind: str
    """run or submit"""
    visible_rate: float | None
    hidden_rate: float | None
    hidden_passed: int
    hidden_total: int


@dataclass(frozen=True)
class Marker:
    ts: int
    minute: float
    level: int
    blocked: bool


@dataclass
class TaskTimeline:
    task_id: str
    points: list[Point] = field(default_factory=list)
    hints: list[Marker] = field(default_factory=list)


@dataclass(frozen=True)
class Paste:
    task_id: str
    minute: float
    chars: int
    large: bool
    after_hint: bool


@dataclass
class Integrity:
    pastes: list[Paste]
    paste_chars: int
    blurs: int
    flags: list[dict[str, Any]]
    """Suspicious-code flags (app/integrity.py) with their task id, deduplicated."""
    refused_writes: list[str]
    extraction_attempts: int


@dataclass(frozen=True)
class Certificate:
    task_id: str
    kind: str
    certified: bool
    """Passed the validation gate (P2.7); older tasks hold boolean placeholders."""
    fields: dict[str, Any]


@dataclass(frozen=True)
class EfficiencyPart:
    name: str
    weight: float
    value: float | None
    evidence: str


@dataclass
class EfficiencyBreakdown:
    value: float
    parts: list[EfficiencyPart]
    extraction_attempts: int
    hints: int
    scale: float
    """min(1, mean_correctness / 50): E is scaled down when correctness is low."""


@dataclass
class ReportDetails:
    candidate_name: str
    tier: str
    breakdown: dict[str, Any]
    certificates: list[Certificate]
    claims: list[Claim]
    timelines: list[TaskTimeline]
    integrity: Integrity
    efficiency: EfficiencyBreakdown | None


class NotGraded(Exception):
    pass


def _ms(moment) -> int:
    return int(moment.timestamp() * 1000)


def _rate(passed: int, total: int) -> float | None:
    return None if total == 0 else round(passed / total, 4)


def profile_of(assessment: Assessment) -> Profile:
    if assessment.profile:
        return Profile.model_validate(assessment.profile)
    return rules_profile(assessment.portfolio)


def timelines(start_ms: int, specs: list[TaskSpec], events: list[Event]) -> list[TaskTimeline]:
    out = {spec.task_id: TaskTimeline(spec.task_id) for spec in specs}

    def minute(ts: int) -> float:
        return round((ts - start_ms) / 60_000, 2)

    for e in events:
        line = out.get(e.task_id)
        if line is None:
            continue
        if e.type in ("run", "submit"):
            visible = e.payload["visible"]
            hidden = e.payload["hidden_silent" if e.type == "run" else "hidden"]
            line.points.append(
                Point(
                    e.ts,
                    minute(e.ts),
                    e.type,
                    _rate(visible["passed"], visible["total"]),
                    _rate(hidden["passed"], hidden["total"]),
                    hidden["passed"],
                    hidden["total"],
                )
            )
        elif e.type == "hint_response":
            line.hints.append(Marker(e.ts, minute(e.ts), e.payload["level"], e.payload["blocked"]))
    return list(out.values())


def integrity(start_ms: int, events: list[Event], runs: list[Run]) -> Integrity:
    hints = [e for e in events if e.type == "hint_response"]
    pastes = []
    for e in events:
        if e.type != "paste":
            continue
        chars = e.payload["chars"]
        after_hint = any(
            h.task_id == e.task_id and h.ts <= e.ts <= h.ts + PASTE_AFTER_HINT_MS for h in hints
        )
        pastes.append(
            Paste(
                e.task_id,
                round((e.ts - start_ms) / 60_000, 2),
                chars,
                chars >= LARGE_PASTE_CHARS,
                after_hint,
            )
        )
    flags: dict[tuple, dict[str, Any]] = {}
    refused: set[str] = set()
    for run in runs:
        for flag in run.integrity.get("flags", []):
            key = (run.task_id, flag["path"], flag["line"], flag["rule"])
            flags.setdefault(key, {"task_id": run.task_id, **flag})
        refused |= set(run.integrity.get("dropped_paths", []))
    return Integrity(
        pastes=pastes,
        paste_chars=sum(p.chars for p in pastes),
        blurs=sum(e.type == "blur" for e in events),
        flags=list(flags.values()),
        refused_writes=sorted(refused),
        extraction_attempts=sum(
            e.type == "hint_request" and e.payload.get("flagged_extraction", False) for e in events
        ),
    )


def efficiency_breakdown(
    e: eff.Efficiency, hints: int, mean_correctness: float
) -> EfficiencyBreakdown:
    def pct(value: float | None) -> str:
        return "n/a" if value is None else f"{round(value * 100)}%"

    parts = [
        EfficiencyPart(
            "Progress per hint",
            eff.WEIGHTS["pph"],
            e.pph,
            f"{pct(e.pph)} of the tests failing at a hint passed within 5 minutes",
        ),
        EfficiencyPart(
            "Tried first",
            eff.WEIGHTS["td"],
            e.td,
            f"{pct(e.td)} of hints came after a run since the previous hint",
        ),
        EfficiencyPart(
            "Run rhythm",
            eff.WEIGHTS["freq"],
            e.freq,
            "1-6 runs per 10 minutes scores full marks",
        ),
        EfficiencyPart(
            "Independence",
            eff.WEIGHTS["ind"],
            e.ind,
            "falls with deeper hints (level 1 costs 1, level 3 costs 3, of 12)",
        ),
    ]
    return EfficiencyBreakdown(
        value=round(e.value, 4),
        parts=parts,
        extraction_attempts=e.extraction_attempts,
        hints=hints,
        scale=round(min(1.0, mean_correctness / 50), 4),
    )


def build(db: Session, session_id: uuid.UUID) -> ReportDetails | None:
    session = db.get(AssessmentSession, session_id)
    if session is None:
        return None
    score = db.scalars(
        select(Score)
        .where(Score.session_id == session.id)
        .order_by(Score.computed_at.desc(), Score.id.desc())
        .limit(1)
    ).first()
    if score is None:
        raise NotGraded
    assessment = db.get(Assessment, session.assessment_id)
    tasks = db.scalars(
        select(Task).where(Task.assessment_id == assessment.id).order_by(Task.order)
    ).all()
    specs = [TaskSpec.model_validate(t.spec) for t in tasks]
    events = db.scalars(
        select(Event).where(Event.session_id == session.id).order_by(Event.ts, Event.id)
    ).all()
    runs = db.scalars(
        select(Run).where(Run.session_id == session.id).order_by(Run.ts, Run.id)
    ).all()
    breakdown = score.breakdown
    correctness = {t["task_id"]: t["correctness"] for t in breakdown["tasks"]}
    start_ms = _ms(session.started_at)

    certificates = []
    for spec in specs:
        fields = spec.certificate.model_dump(mode="json")
        fields["scope_files"] = [str(p) for p in fields.get("scope_files", [])]
        certified = not isinstance(spec.certificate.reference_pass, bool)
        certificates.append(Certificate(spec.task_id, spec.kind, certified, fields))

    efficiency = None
    if assessment.tier != "novice":
        mean = breakdown["mean_correctness"]
        hints = sum(e.type == "hint_response" for e in events)
        efficiency = efficiency_breakdown(ai_efficiency(db, session, specs, mean), hints, mean)
    return ReportDetails(
        candidate_name=assessment.candidate_name,
        tier=assessment.tier,
        breakdown=breakdown,
        certificates=certificates,
        claims=claim_map(profile_of(assessment), specs, correctness),
        timelines=timelines(start_ms, specs, events),
        integrity=integrity(start_ms, events, runs),
        efficiency=efficiency,
    )
