"""AI voice interview (F5), keyed by the session id. Report only, never scored.

Recruiter (X-Recruiter-Key): POST /interviews/{id} sets it up for a submitted session (one
generator call builds the plan), GET /interviews/{id}/report gives the transcript and the
"x of y submission facts" check. Candidate: GET /interviews/{id}, POST .../start (consent),
POST .../turn, POST .../end, GET .../audio/{hash} (Featherless TTS through backend/llm,
cached; only text the interviewer says in this interview). The candidate view never holds
the expected facts.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.models import Assessment, AssessmentSession, Interview
from app.recruiter import require_recruiter
from app.routes.sessions import DbSession
from interviewer import interview as iv
from interviewer.facts import session_changes
from interviewer.plan import Setup, build_plan

logger = logging.getLogger("interviewer")

router = APIRouter(prefix="/interviews", tags=["interviews"])


class SetupIn(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    job_description: str = Field(default="", max_length=6000)
    focus: str = Field(default="", max_length=600)


class StartIn(BaseModel):
    consent: bool


class TurnIn(BaseModel):
    answer_text: str = Field(max_length=iv.ANSWER_CHARS)


def _audio_url(session_id: uuid.UUID, text: str) -> str:
    return f"/interviews/{session_id}/audio/{iv.segment_hash(text)}"


def _say(session_id: uuid.UUID, turn: dict, row: Interview) -> dict[str, Any]:
    return {
        "say_text": turn["text"],
        "segments": [{"text": s, "audio_url": _audio_url(session_id, s)} for s in turn["segments"]],
        "kind": turn["kind"],
        "state": _state(row),
    }


def _state(row: Interview) -> dict[str, Any]:
    questions = row.plan["questions"]
    cursor = min(row.state["cursor"], len(questions))
    return {
        "status": row.status,
        "question_index": cursor,
        "question_count": len(questions),
        "blocks": [q["block"] for q in questions],
        "started_ms": row.state.get("started_ms"),
        "max_seconds": iv.MAX_SECONDS,
    }


def _candidate_view(row: Interview) -> dict[str, Any]:
    transcript = [
        {k: t[k] for k in ("speaker", "text", "question_id", "ts") if k in t}
        for t in row.transcript
    ]
    return {
        "company": row.setup["company"],
        "role": row.setup["role"],
        "state": _state(row),
        "transcript": transcript,
    }


def _locked(db: DbSession, session_id: uuid.UUID) -> Interview:
    row = db.get(Interview, session_id, with_for_update=True)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no interview is set up for this session")
    return row


def _save(row: Interview, machine: iv.Interview) -> None:
    # New objects so SQLAlchemy sees the JSONB changes.
    row.state = dict(machine.state)
    row.transcript = list(machine.transcript)
    if machine.done:
        row.status = "done"
        row.ended_at = datetime.now(UTC)


def _machine(row: Interview) -> iv.Interview:
    return iv.Interview(row.plan, row.state, row.transcript, row.setup)


def warm_audio(lines: list[str]) -> None:
    """Synthesize the scripted lines ahead of time so the interview doesn't wait on TTS."""
    from llm import synthesize_speech

    for line in lines:
        try:
            synthesize_speech(line)
        except Exception as exc:  # noqa: BLE001 - the UI falls back to the browser voice
            logger.warning("tts warm-up failed: %s", type(exc).__name__)
            return


@router.post("/{session_id}", dependencies=[Depends(require_recruiter)], status_code=201)
def set_up(
    session_id: uuid.UUID, body: SetupIn, db: DbSession, background: BackgroundTasks
) -> dict[str, Any]:
    session = db.get(AssessmentSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    if session.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "the session is not submitted yet")
    if db.get(Interview, session_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "an interview is already set up")
    portfolio = session_portfolio(db, session)
    setup = Setup(**body.model_dump())
    plan = build_plan(setup, portfolio, session_changes(db, session)).to_dict()
    row = Interview(
        session_id=session_id,
        setup=body.model_dump(),
        plan=plan,
        state=iv.initial_state(),
        transcript=[],
        status="planned",
    )
    db.add(row)
    db.commit()
    background.add_task(warm_audio, iv.scripted_lines(plan, row.setup))
    return {"session_id": str(session_id), "url": f"/interview/{session_id}", "plan": plan}


def session_portfolio(db: DbSession, session: AssessmentSession) -> dict[str, Any]:
    assessment = db.get(Assessment, session.assessment_id)
    return assessment.portfolio if assessment else {}


@router.get("/{session_id}")
def get_interview(session_id: uuid.UUID, db: DbSession) -> dict[str, Any]:
    row = db.get(Interview, session_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no interview is set up for this session")
    return _candidate_view(row)


@router.post("/{session_id}/start")
def start(session_id: uuid.UUID, body: StartIn, db: DbSession) -> dict[str, Any]:
    if not body.consent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "consent is required")
    row = _locked(db, session_id)
    if row.status != "planned":
        raise HTTPException(status.HTTP_409_CONFLICT, "the interview has already started")
    machine = _machine(row)
    turn = machine.start()
    row.status = "live"
    row.consent_at = datetime.now(UTC)
    _save(row, machine)
    db.commit()
    return _say(session_id, turn, row)


@router.post("/{session_id}/turn")
def turn(session_id: uuid.UUID, body: TurnIn, db: DbSession) -> dict[str, Any]:
    row = _locked(db, session_id)
    if row.status != "live":
        raise HTTPException(status.HTTP_409_CONFLICT, f"the interview is {row.status}")
    machine = _machine(row)
    try:
        said = machine.turn(body.answer_text)
    except iv.InterviewError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    _save(row, machine)
    db.commit()
    return _say(session_id, said, row)


@router.post("/{session_id}/end")
def end(session_id: uuid.UUID, db: DbSession) -> dict[str, Any]:
    row = _locked(db, session_id)
    if row.status != "live":
        raise HTTPException(status.HTTP_409_CONFLICT, f"the interview is {row.status}")
    machine = _machine(row)
    said = machine.end()
    _save(row, machine)
    db.commit()
    return _say(session_id, said, row)


@router.get("/{session_id}/audio/{digest}")
def audio(session_id: uuid.UUID, digest: str, db: DbSession) -> Response:
    from llm import synthesize_speech

    row = db.get(Interview, session_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no interview is set up for this session")
    text = iv.spoken_segments(row.transcript, row.plan, row.setup).get(digest)
    if text is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "the interviewer did not say that")
    try:
        mp3 = synthesize_speech(text)
    except Exception as exc:  # noqa: BLE001 - the UI falls back to the browser voice
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"speech unavailable: {type(exc).__name__}"
        ) from None
    return Response(
        mp3, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"}
    )


@router.get("/{session_id}/report", dependencies=[Depends(require_recruiter)])
def report(session_id: uuid.UUID, db: DbSession) -> dict[str, Any]:
    row = db.get(Interview, session_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no interview is set up for this session")
    return {
        "setup": row.setup,
        "status": row.status,
        "consent_at": row.consent_at.isoformat() if row.consent_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "questions": [
            {k: q[k] for k in ("id", "block", "text", "source")} for q in row.plan["questions"]
        ],
        "transcript": [
            {k: t.get(k) for k in ("speaker", "kind", "text", "question_id", "ts", "llm_used")}
            for t in row.transcript
        ],
        "facts": iv.facts_report(row.plan, row.transcript),
        "tokens": {
            "plan": row.plan["tokens"],
            "turns": row.state["tokens"],
            "budget": iv.token_budget(),
            "llm_calls": row.state["llm_calls"],
        },
        "label": "Interview: not scored",
    }
