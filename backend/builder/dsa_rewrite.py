"""Rewrite a bank problem into the candidate's domain (P2.6).

One generator call per distinct input (problem, domain, project names), cached by the LLM
client. The model writes only a story and new names; code adds the function section and
the worked examples (builder.dsa_bank.statement_md). A reply is used only if the names map
1:1 to valid identifiers in Python and JS, the story doesn't copy the original, and the
reference behind the renamed wrapper still gives the expected output on every case.
Otherwise one retry, then a template statement built by code with the original names.
"""

import builtins
import keyword
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from builder.dsa_bank import BankProblem, identity_names
from contracts_gen.task_spec import DsaNames, NameMapping
from llm import complete_structured
from llm.client import summarize_error

logger = logging.getLogger(__name__)

MAX_TOKENS = 600
TEMPERATURE = 0.2
DESCRIPTION_CHARS = 2000
STORY_CHARS = 2500
COPIED_WORDS = 8
"""A run of this many words shared with the original description counts as copying."""
NAME = re.compile(r"[a-z][a-z0-9_]{0,39}")
JS_RESERVED = frozenset(
    "break case catch class const continue debugger default delete do else enum export "
    "extends false finally for function if implements import in instanceof interface let "
    "new null package private protected public return static super switch this throw true "
    "try typeof var void while with yield await arguments eval undefined NaN Infinity "
    "module exports require globalThis console".split()
)
PY_RESERVED = frozenset(keyword.kwlist + keyword.softkwlist + dir(builtins))
DOMAIN_SETTING = {
    "backend": "backend web services and APIs",
    "web": "frontend web applications",
    "ml": "machine learning and data pipelines",
    "security": "security tooling and log analysis",
}
SYSTEM = (
    "You retell programming puzzles as short tasks set in a software team's day-to-day "
    "work. The computation must stay exactly the same. Reply with JSON only."
)

Llm = Callable[..., BaseModel]
Check = Callable[[DsaNames], str | None]


class RenamedParameter(BaseModel):
    original: str
    renamed: str = Field(description="new snake_case name")


class DsaRewrite(BaseModel):
    statement: str = Field(
        description="Markdown, 80-250 words, no heading above ##: the same problem told in "
        "the given domain, keeping every rule, constraint and edge case. No examples, no "
        "code, no hints on how to solve it."
    )
    function_name: str = Field(description="new snake_case function name that fits the story")
    parameters: list[RenamedParameter] = Field(description="one entry per original parameter")


class RewriteRejected(ValueError):
    pass


@dataclass
class Rewritten:
    story: str
    names: DsaNames
    source: Literal["llm", "template"]
    notes: list[str] = field(default_factory=list)


def rewrite_problem(
    problem: BankProblem,
    domain: str,
    project_names: list[str],
    check: Check,
    llm: Llm = complete_structured,
) -> Rewritten:
    notes: list[str] = []
    description = load_description(problem)
    if description is None:
        note = f"no description for {problem.id} (dsa/raw/ missing); template statement used"
        logger.warning(note)
        return Rewritten(template_story(problem), identity_names(problem), "template", [note])

    messages = prompt(problem, description, domain, project_names)
    for attempt in (1, 2):
        try:
            reply = llm(
                "generator",
                messages,
                DsaRewrite,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            names = validate_reply(problem, reply, description)
            mismatch = check(names)
            if mismatch is not None:
                raise RewriteRejected(mismatch)
        except RewriteRejected as exc:
            notes.append(f"rewrite attempt {attempt} rejected: {exc}")
            # A different conversation, so the retry isn't answered from the cache.
            messages = messages + [
                {"role": "assistant", "content": reply.model_dump_json()},
                {"role": "user", "content": f"Rejected: {exc}. Fix that and answer again."},
            ]
        except Exception as exc:  # noqa: BLE001 - any LLM failure falls back to the template
            notes.append(f"rewrite attempt {attempt} failed: {summarize_error(exc)}")
            break
        else:
            return Rewritten(reply.statement.strip(), names, "llm", notes)
    notes.append("template statement used")
    logger.warning("DSA rewrite of %s fell back to the template: %s", problem.id, notes)
    return Rewritten(template_story(problem), identity_names(problem), "template", notes)


def load_description(problem: BankProblem) -> str | None:
    """Our own problem.md, or the original description cached in dsa/raw/ (never committed)."""
    if problem.own_statement:
        return (problem.dir / "problem.md").read_text(encoding="utf-8")
    path = problem.dir.parent / "raw" / "descriptions" / f"{problem.id}.md"
    return path.read_text(encoding="utf-8") if path.is_file() else None


def trim_description(description: str) -> str:
    """Drop the worked examples (code adds its own); keep the rules and the constraints."""
    head, sep, rest = description.partition("Example 1")
    constraints = rest[rest.find("Constraints:") :] if sep and "Constraints:" in rest else ""
    text = (head.strip() + "\n\n" + constraints.strip()).strip()
    return text[:DESCRIPTION_CHARS]


def prompt(
    problem: BankProblem, description: str, domain: str, project_names: list[str]
) -> list[dict[str, str]]:
    params = "\n".join(f"- {p.name}: {p.type}" for p in problem.signature.params)
    projects = ", ".join(name[:40] for name in project_names[:3]) or "none given"
    user = (
        f"Domain: {DOMAIN_SETTING.get(domain, domain)}. Candidate's projects: {projects}.\n"
        f"Function: {problem.entry_point}, returns {problem.signature.returns}\n"
        f"Parameters, in order:\n{params}\n\n"
        f"Original puzzle:\n<<<\n{trim_description(description)}\n>>>\n\n"
        "Retell it as a task in that domain (you may mention a project). Do not copy "
        "sentences from the original. Choose a new function name and one new name per "
        "parameter, all snake_case, that fit the story."
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def validate_reply(problem: BankProblem, reply: DsaRewrite, description: str) -> DsaNames:
    """The renaming as DsaNames; raises RewriteRejected if the reply can't be used as is."""
    originals = [p.name for p in problem.signature.params]
    got = [p.original for p in reply.parameters]
    if sorted(got) != sorted(originals):
        raise RewriteRejected(f"parameters must rename exactly {originals}, got {got}")
    new = {p.original: p.renamed for p in reply.parameters}
    renamed = [reply.function_name] + [new[name] for name in originals]
    for name in renamed:
        if why := invalid_name(name):
            raise RewriteRejected(f"{name!r} {why}")
    if len(set(renamed)) != len(renamed):
        raise RewriteRejected(f"names must all differ: {renamed}")
    story = reply.statement.strip()
    if not story or len(story) > STORY_CHARS:
        raise RewriteRejected(f"the statement must be 1-{STORY_CHARS} characters")
    if copied := copied_words(story, description):
        raise RewriteRejected(f"the statement copies the original: {copied!r}")
    stale = [o for o in originals if new[o] != o and f"`{o}`" in story]
    if stale:
        raise RewriteRejected(f"the statement still uses the old names {stale}; use the new ones")
    return DsaNames(
        function=NameMapping(original=problem.entry_point, renamed=reply.function_name),
        parameters=[NameMapping(original=name, renamed=new[name]) for name in originals],
    )


def invalid_name(name: str) -> str | None:
    if not NAME.fullmatch(name):
        return "is not a snake_case identifier (a-z, 0-9, _; at most 40 characters)"
    if name in PY_RESERVED or name in JS_RESERVED:
        return "is reserved or built in (Python or JavaScript)"
    if name.startswith("_bank"):
        return "is reserved"
    return None


def copied_words(story: str, description: str) -> str | None:
    """The first run of COPIED_WORDS words the story shares with the description, if any."""

    def words(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    original = words(description)
    runs = {tuple(original[i : i + COPIED_WORDS]) for i in range(len(original) - COPIED_WORDS + 1)}
    told = words(story)
    for i in range(len(told) - COPIED_WORDS + 1):
        if tuple(told[i : i + COPIED_WORDS]) in runs:
            return " ".join(told[i : i + COPIED_WORDS])
    return None


def template_story(problem: BankProblem) -> str:
    """Statement built by code: our own problem.md, else a generic task from the metadata."""
    if problem.own_statement:
        return (problem.dir / "problem.md").read_text(encoding="utf-8")
    title = problem.entry_point.replace("_", " ").capitalize()
    topics = ", ".join(tag.replace("_", " ") for tag in problem.tags)
    return (
        f"## {title}\n\n"
        f"Implement `{problem.entry_point}` so that it returns the expected result for every "
        "input. The examples below show the exact input and output format; the hidden cases "
        f"use more inputs of the same shape, including edge cases.\n\nTopics: {topics}."
    )
