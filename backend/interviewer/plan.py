"""The interview plan: 5 questions from one generator call, cached by input hash.

2 role questions from the recruiter's company and role text, 1 about a portfolio project,
2 about the candidate's submitted change (one per task, or two on the only task). The model
sees the recruiter's text, one project and the candidate's own diff: never the reference or
hidden tests (CLAUDE.md rule 2). A question that fails the guards, or the whole plan when
the call fails, falls back to a template, so an interview always has 5 questions.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from interviewer import guards
from interviewer.facts import Fact, TaskChange

logger = logging.getLogger("interviewer")

PLAN_MAX_TOKENS = 400
PLAN_TEMPERATURE = 0.2
JOB_CHARS = 1500
QUESTION_CHARS = 240

SYSTEM_PROMPT = """\
You write the questions for a short, friendly AI voice interview held right after a coding
assessment. Every question is one spoken sentence, under 30 words, with no code. Use only
the company and role text you are given; do not invent facts about the company. Never ask
about age, religion, family, marriage, children, nationality, ethnicity, gender, health or
disability, or politics. Submission questions ask the candidate to explain their own change
(which function or file they changed, why, how they checked it); never say or hint whether
the change was correct and never describe a solution. Reply with JSON only."""


class PlanDraft(BaseModel):
    role_questions: list[str] = Field(min_length=2, max_length=2)
    portfolio_question: str
    submission_questions: list[str] = Field(min_length=2, max_length=2)


@dataclass(frozen=True)
class Setup:
    company: str
    role: str
    job_description: str = ""
    focus: str = ""


@dataclass
class Question:
    id: str
    block: str
    """role | portfolio | submission"""
    text: str
    source: str
    """model | template"""
    task_id: str | None = None
    facts: list[Fact] = field(default_factory=list)


@dataclass
class Plan:
    questions: list[Question]
    tokens: int
    source: str
    """model: the generator wrote it (some questions may still be templates). template: no call."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_from_dict(data: dict[str, Any]) -> Plan:
    questions = [
        Question(**{**q, "facts": [Fact(**f) for f in q.get("facts", [])]})
        for q in data["questions"]
    ]
    return Plan(questions=questions, tokens=data["tokens"], source=data["source"])


def pick_project(portfolio: dict[str, Any]) -> dict[str, Any] | None:
    projects = [p for p in portfolio.get("projects") or [] if p.get("name")]
    with_highlights = [p for p in projects if p.get("highlights")]
    return (with_highlights or projects or [None])[0]


def submission_targets(changes: list[TaskChange]) -> list[TaskChange]:
    """Two changes to ask about: the domain task's then the DSA task's (or one twice)."""
    ordered = sorted(changes, key=lambda c: c.kind != "domain")
    if not ordered:
        return []
    return [ordered[0], ordered[1] if len(ordered) > 1 else ordered[0]]


def templates(setup: Setup, project: dict[str, Any] | None, targets: list[TaskChange]) -> PlanDraft:
    if project and project.get("highlights"):
        portfolio = (
            f"In {project['name']} you mention: {project['highlights'][0].rstrip('.')}. "
            "How did you do that, and what would you change now?"
        )
    elif project:
        portfolio = f"Tell me about {project['name']}: what was the hardest part you built?"
    else:
        portfolio = "Tell me about a project you are proud of: what was the hardest part?"
    first = targets[0].title if targets else "the coding"
    second = targets[1].title if len(targets) > 1 else first
    return PlanDraft(
        role_questions=[
            f"What draws you to the {setup.role} role at {setup.company}, and which part of "
            "the work would you want to own first?",
            "Tell me about a time you had to learn an unfamiliar codebase quickly. How did you "
            "find your way around?",
        ],
        portfolio_question=portfolio,
        submission_questions=[
            f"In the {first} task, could you walk me through what you changed and why?",
            f"For the {second} task, how did you check that your change was correct?",
        ],
    )


def messages(
    setup: Setup, project: dict[str, Any] | None, targets: list[TaskChange]
) -> list[dict[str, str]]:
    payload = {
        "company": setup.company,
        "role": setup.role,
        "job_description": setup.job_description[:JOB_CHARS],
        "focus": setup.focus[:300],
        "portfolio_project": None
        if project is None
        else {
            "name": project.get("name"),
            "description": project.get("description", ""),
            "highlights": (project.get("highlights") or [])[:3],
        },
        "submissions": [
            {
                "task": t.title,
                "kind": t.kind,
                "files": t.files,
                "functions": t.functions,
                "diff": t.diff,
            }
            for t in targets
        ],
    }
    shape = (
        '{"role_questions": [2 questions about the role and company], '
        '"portfolio_question": "1 question about the portfolio project", '
        '"submission_questions": [1 question per submission, in order]}'
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Reply as {shape}.\n\n{json.dumps(payload, indent=1)}"},
    ]


def _clean(text: str) -> str:
    return " ".join(text.split())[:QUESTION_CHARS]


def build_plan(
    setup: Setup,
    portfolio: dict[str, Any],
    changes: list[TaskChange],
    call=None,
) -> Plan:
    """`call(messages) -> (PlanDraft, tokens)`; defaults to the generator slot."""
    project = pick_project(portfolio)
    targets = submission_targets(changes)
    fallback = templates(setup, project, targets)
    draft, tokens, source = fallback, 0, "template"
    try:
        draft, tokens = (call or _generator)(messages(setup, project, targets))
        source = "model"
    except Exception as exc:  # noqa: BLE001 - the templates keep the interview usable
        logger.warning(
            json.dumps({"event": "interview_plan_fallback", "error": type(exc).__name__})
        )

    def pick(text: str, template: str) -> tuple[str, str]:
        text = _clean(text)
        if source == "model" and guards.problem(text) is None and len(text.split()) >= 3:
            return text, "model"
        return template, "template"

    questions: list[Question] = []
    for i, (q, t) in enumerate(zip(draft.role_questions, fallback.role_questions, strict=True)):
        text, src = pick(q, t)
        questions.append(Question(f"role-{i + 1}", "role", text, src))
    text, src = pick(draft.portfolio_question, fallback.portfolio_question)
    questions.append(Question("portfolio-1", "portfolio", text, src))
    pairs = zip(draft.submission_questions, fallback.submission_questions, strict=True)
    for i, ((q, t), target) in enumerate(zip(pairs, targets or [None, None], strict=True)):
        text, src = pick(q, t)
        questions.append(
            Question(
                f"submission-{i + 1}",
                "submission",
                text,
                src,
                task_id=target.task_id if target else None,
                facts=list(target.facts) if target else [],
            )
        )
    return Plan(questions=questions, tokens=tokens, source=source)


def _generator(msgs: list[dict[str, str]]) -> tuple[PlanDraft, int]:
    from llm import default_client

    draft, info = default_client().structured(
        "generator",
        msgs,
        PlanDraft,
        temperature=PLAN_TEMPERATURE,
        max_retries=2,
        max_tokens=PLAN_MAX_TOKENS,
    )
    return draft, info.prompt_tokens + info.completion_tokens
