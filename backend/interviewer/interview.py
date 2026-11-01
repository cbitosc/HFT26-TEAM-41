"""The interview itself: start, turns, end, and the recruiter's view of it.

Plain code decides first (docs/INTERVIEWER.md token rules): time up -> closing; a request
for solutions -> scripted refusal; a short answer -> scripted nudge; the follow-up already
used, every expected fact mentioned, or the token budget spent -> scripted acknowledgement
and the next question. Otherwise one interviewer-slot call (max_tokens 120, no history)
replies conversationally: either one follow-up question or an acknowledgement. Its reply
goes through interviewer.guards; anything it may not say is replaced by scripted text.
At most one follow-up per question. Nothing here feeds a score (CLAUDE.md rule 8).
"""

import hashlib
import json
import logging
import os
import re
import time
from typing import Any

from assistant.guards import extraction_reason
from interviewer import guards
from interviewer.facts import Fact, mentions, words
from interviewer.plan import Plan, Question, plan_from_dict

logger = logging.getLogger("interviewer")

TURN_MAX_TOKENS = 120
TURN_TEMPERATURE = 0.2
ANSWER_WORDS = 120
ANSWER_CHARS = 4000
SHORT_ANSWER_WORDS = 12
MAX_LLM_CALLS = 10
MAX_SECONDS = 12 * 60
DEFAULT_TOKEN_BUDGET = 4000

GREETING = (
    "Hi, I'm an AI interviewer for {company}. This is a short voice interview about the "
    "{role} role, one of your projects and the code you just submitted: {n} questions, about "
    "ten minutes. It doesn't change your score, and you can speak or type your answers. "
    "Let's begin."
)
CLOSING = (
    "That's all my questions. Thank you for talking me through your work. The transcript "
    "goes to the recruiter with your report, and it doesn't change your score. Goodbye!"
)
TIME_UP = "We're out of time, so let's stop here. Thank you, that was helpful. Goodbye!"
ENDED = "Okay, let's stop here. Thank you for your time. Goodbye!"
ACKS = ("Thanks.", "Got it, thank you.", "Okay, that's helpful.", "Thanks for explaining.")
NUDGE = "Could you say a little more about that? An example from your own work would help."
REFUSAL = "I can't share solutions or tests, but I'd like to hear your own thinking."

SYSTEM_PROMPT = """\
You are a friendly AI interviewer in a short voice interview after a coding assessment.
You get the current question and the candidate's answer. Reply in exactly one line:
FOLLOW_UP: <one short follow-up question about something specific in the answer>
or
NEXT: <one short sentence acknowledging the answer, no question>
Use FOLLOW_UP only when the answer is vague or skips the why. Under 30 words. Never write
code, never say whether their code is right, never describe a solution or tests, never ask
about age, religion, family, nationality, health or other personal matters. If the answer
asks for a solution or is off topic, decline politely with NEXT."""

_REPLY = re.compile(r"^\W*(FOLLOW[_ ]?UP|NEXT)\W*:?\s*(.+)$", re.IGNORECASE | re.DOTALL)


class InterviewError(Exception):
    status = 409


def token_budget() -> int:
    return int(os.environ.get("INTERVIEW_TOKEN_BUDGET", DEFAULT_TOKEN_BUDGET))


def now_ms() -> int:
    return int(time.time() * 1000)


def segment_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def initial_state() -> dict[str, Any]:
    return {"cursor": 0, "followup_used": False, "llm_calls": 0, "tokens": 0, "started_ms": None}


# --- Model call -----------------------------------------------------------------------


def _interviewer_call(msgs: list[dict[str, str]]) -> tuple[str, int]:
    from llm import default_client

    text, info = default_client().text(
        "interviewer", msgs, temperature=TURN_TEMPERATURE, max_tokens=TURN_MAX_TOKENS
    )
    return text, info.prompt_tokens + info.completion_tokens


def turn_messages(question: Question, answer: str, missing: list[Fact]) -> list[dict[str, str]]:
    trimmed = " ".join(answer.split()[:ANSWER_WORDS])
    user = f"Question: {question.text}\nAnswer: {trimmed}"
    if missing:
        user += "\nNot mentioned yet: " + ", ".join(f.label for f in missing)
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def parse_reply(text: str) -> tuple[str, str]:
    """("follow_up" | "next", text) from the model's one-line reply."""
    line = text.strip().strip('"').strip()
    match = _REPLY.match(line)
    if match:
        action = "next" if match.group(1).upper() == "NEXT" else "follow_up"
        body = match.group(2)
    else:
        body = line
        action = "follow_up" if body.rstrip().endswith("?") else "next"
    body = " ".join(body.split()).strip('"').strip()
    if action == "next" and body.endswith("?"):
        action = "follow_up"
    return action, body


# --- State machine --------------------------------------------------------------------


class Interview:
    """Wraps the stored row's plan, state and transcript; the route saves them back."""

    def __init__(self, plan: dict[str, Any], state: dict[str, Any], transcript: list, setup: dict):
        self.plan: Plan = plan_from_dict(plan)
        self.state = dict(state)
        self.transcript = list(transcript)
        self.setup = setup
        self.done = False

    @property
    def question(self) -> Question | None:
        cursor = self.state["cursor"]
        return self.plan.questions[cursor] if cursor < len(self.plan.questions) else None

    def _say(self, segments: list[str], kind: str, llm_used: bool = False, tokens: int = 0) -> dict:
        q = self.question
        turn = {
            "speaker": "interviewer",
            "kind": kind,
            "text": " ".join(segments),
            "segments": segments,
            "question_id": q.id if q else None,
            "ts": now_ms(),
            "llm_used": llm_used,
            "tokens": tokens,
        }
        self.transcript.append(turn)
        return turn

    def start(self) -> dict:
        self.state["started_ms"] = now_ms()
        greeting = GREETING.format(
            company=self.setup["company"], role=self.setup["role"], n=len(self.plan.questions)
        )
        return self._say([greeting, self.plan.questions[0].text], "question")

    def _advance(self, ack: str, llm_used: bool = False, tokens: int = 0) -> dict:
        self.state["cursor"] += 1
        self.state["followup_used"] = False
        q = self.question
        if q is None:
            self.done = True
            return self._say([ack, CLOSING], "closing", llm_used, tokens)
        return self._say([ack, q.text], "question", llm_used, tokens)

    def _ack(self) -> str:
        return ACKS[(self.state["cursor"] + len(self.transcript)) % len(ACKS)]

    def answers(self, question_id: str) -> str:
        return " ".join(
            t["text"]
            for t in self.transcript
            if t["speaker"] == "candidate" and t["question_id"] == question_id
        )

    def _over_budget(self, msgs: list[dict[str, str]]) -> bool:
        estimate = sum(len(m["content"]) for m in msgs) // 4 + TURN_MAX_TOKENS
        return (
            self.state["llm_calls"] >= MAX_LLM_CALLS
            or self.state["tokens"] + estimate > token_budget()
        )

    def turn(self, answer: str, call=None) -> dict:
        q = self.question
        if q is None:
            raise InterviewError("the interview is over")
        answer = answer.strip()[:ANSWER_CHARS]
        self.transcript.append(
            {"speaker": "candidate", "text": answer, "question_id": q.id, "ts": now_ms()}
        )
        started = self.state.get("started_ms") or now_ms()
        if (now_ms() - started) / 1000 >= MAX_SECONDS:
            self.done = True
            return self._say([TIME_UP], "closing")

        followup_used = self.state["followup_used"]
        if extraction_reason(answer):
            if followup_used:
                return self._advance(REFUSAL)
            self.state["followup_used"] = True
            return self._say([REFUSAL, q.text], "follow_up")
        if len(words(answer)) < SHORT_ANSWER_WORDS and not followup_used:
            self.state["followup_used"] = True
            return self._say([NUDGE], "follow_up")
        if followup_used:
            return self._advance(self._ack())

        so_far = self.answers(q.id)
        missing = [f for f in q.facts if not mentions(so_far, f)]
        if q.facts and not missing:
            return self._advance(self._ack())

        msgs = turn_messages(q, answer, missing)
        if self._over_budget(msgs):
            logger.info(json.dumps({"event": "interview_scripted", "reason": "budget"}))
            return self._advance(self._ack())
        try:
            text, tokens = (call or _interviewer_call)(msgs)
        except Exception as exc:  # noqa: BLE001 - scripted text keeps the interview going
            logger.warning(
                json.dumps({"event": "interview_llm_error", "error": type(exc).__name__})
            )
            return self._advance(self._ack())
        self.state["llm_calls"] += 1
        self.state["tokens"] += tokens
        logger.info(
            json.dumps({"event": "interview_turn", "tokens": tokens, "total": self.state["tokens"]})
        )
        action, reply = parse_reply(text)
        why = guards.problem(reply)
        if why is not None:
            logger.info(json.dumps({"event": "interview_guard", "reason": why}))
            return self._advance(self._ack(), llm_used=True, tokens=tokens)
        if action == "follow_up":
            self.state["followup_used"] = True
            return self._say([reply], "follow_up", llm_used=True, tokens=tokens)
        return self._advance(reply, llm_used=True, tokens=tokens)

    def end(self) -> dict:
        self.done = True
        return self._say([ENDED], "closing")


# --- Views ----------------------------------------------------------------------------


def spoken_segments(transcript: list, plan: dict[str, Any], setup: dict) -> dict[str, str]:
    """hash -> text of everything the interviewer said or will say (for the audio route)."""
    texts = [s for t in transcript if t["speaker"] == "interviewer" for s in t["segments"]]
    return {segment_hash(t): t for t in texts + scripted_lines(plan, setup)}


def scripted_lines(plan: dict[str, Any], setup: dict) -> list[str]:
    questions = [q["text"] for q in plan["questions"]]
    greeting = GREETING.format(company=setup["company"], role=setup["role"], n=len(questions))
    return [greeting, *questions, CLOSING, TIME_UP, ENDED, NUDGE, REFUSAL, *ACKS]


def facts_report(plan: dict[str, Any], transcript: list) -> dict[str, Any]:
    """Per submission question: which expected facts the candidate's answers mentioned.

    A fact asked about twice (one task, two questions) counts once in the total, and as
    mentioned if either answer mentioned it.
    """
    rows, keys, mentioned = [], set(), set()
    for q in plan_from_dict(plan).questions:
        if q.block != "submission":
            continue
        said = " ".join(
            t["text"]
            for t in transcript
            if t["speaker"] == "candidate" and t["question_id"] == q.id
        )
        facts = [{"label": f.label, "mentioned": mentions(said, f)} for f in q.facts]
        rows.append({"question_id": q.id, "task_id": q.task_id, "text": q.text, "facts": facts})
        for f in facts:
            keys.add((q.task_id, f["label"]))
            if f["mentioned"]:
                mentioned.add((q.task_id, f["label"]))
    return {"questions": rows, "mentioned": len(mentioned), "total": len(keys)}
