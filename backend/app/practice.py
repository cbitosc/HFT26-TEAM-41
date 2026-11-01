"""Practice mode: the DSA bank as a LeetCode-style problem set, no assessment session.

A visitor picks a bank problem, writes a solution in Python or JavaScript, then Runs it on
the visible examples (or on one custom input) or Submits it for the hidden cases. All
code runs through app.dsa in the same sandbox as assessments; this module only builds the
task spec for a problem and shapes results. Hidden cases never leave the backend: a
Submit result is pass counts and a status, never a case, an input, an expected value or
program output. Only practice-only bank problems exist here (BankProblem.practice_only),
so practice never shows a problem an assessment can pick.
"""

import json
from functools import lru_cache
from typing import Any, Literal

from app import dsa
from builder.dsa_bank import BankProblem, identity_names, load_bank, task_spec
from contracts_gen.task_spec import DsaCase, TaskSpec

LANGUAGES = {"python": "python311", "javascript": "node20"}
Language = Literal["python", "javascript"]

PRACTICE_TIER = "novice"
HIDDEN_SEED_KEY = "practice"
MAX_CODE_CHARS = 100_000
MAX_CUSTOM_INPUT_CHARS = 20_000
SHOWN_OUTPUT_CHARS = 2000
CUSTOM_CASE_ID = "custom"

_STORY_END = "## Your function"


@lru_cache
def _by_id() -> dict[str, BankProblem]:
    return {p.id: p for p in load_problems()}


def load_problems() -> tuple[BankProblem, ...]:
    """The practice-only bank problems."""
    return tuple(p for p in load_bank() if p.practice_only)


def get_problem(problem_id: str) -> BankProblem | None:
    return _by_id().get(problem_id)


def _problem_md(problem: BankProblem) -> str:
    return (problem.dir / "problem.md").read_text(encoding="utf-8")


def title(problem: BankProblem) -> str:
    """The first "## Heading" of problem.md, else the id as words."""
    for line in _problem_md(problem).splitlines():
        if line.startswith("## "):
            return line[3:].strip()
    return problem.id.replace("_", " ").capitalize()


def story(problem: BankProblem) -> str:
    """problem.md before "## Your function", without its title line."""
    text = _problem_md(problem).split(_STORY_END)[0]
    lines = text.splitlines()
    if lines and lines[0].startswith("## "):
        lines = lines[1:]
    return "\n".join(lines).strip()


@lru_cache
def spec_for(problem_id: str, language: str) -> TaskSpec:
    """The (identity-named) DSA task for a problem in a language. Needs no Docker."""
    problem = _by_id()[problem_id]
    names = identity_names(problem)
    runtime = LANGUAGES[language]
    spec = task_spec(problem, story(problem), names, runtime, PRACTICE_TIER)
    return TaskSpec.model_validate(spec)


def solution_path(problem_id: str, language: str) -> str:
    return dsa.entry_point(spec_for(problem_id, language))[0]


def parameter_names(spec: TaskSpec) -> list[str]:
    assert spec.dsa_names is not None
    return [p.renamed for p in spec.dsa_names.parameters]


def parse_custom_input(spec: TaskSpec, raw: str) -> dict[str, Any]:
    """A JSON object with exactly the function's parameters, or ValueError(why)."""
    if len(raw) > MAX_CUSTOM_INPUT_CHARS:
        raise ValueError("custom input is too long")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"custom input is not valid JSON: {exc.msg}") from exc
    names = parameter_names(spec)
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError(f"custom input must be a JSON object with the keys: {', '.join(names)}")
    return value


# --- Execution (called by the Celery worker) -----------------------------------------


def _files(problem_id: str, language: str, code: str) -> dict[str, str]:
    return {solution_path(problem_id, language): code}


def run_visible(problem_id: str, language: str, code: str) -> dict[str, Any]:
    spec = spec_for(problem_id, language)
    cases = spec.dsa_cases.visible
    result = dsa.run_cases(spec, _files(problem_id, language, code), cases, [c.id for c in cases])
    return {"kind": "run", "result": result.model_dump(mode="json")}


def run_custom(problem_id: str, language: str, code: str, custom: dict[str, Any]) -> dict[str, Any]:
    spec = spec_for(problem_id, language)
    case = DsaCase(id=CUSTOM_CASE_ID, input=custom, expected=None)
    run = dsa.execute_cases(spec, _files(problem_id, language, code), [case])
    out: dict[str, Any] = {
        "kind": "custom",
        "status": run.status,
        "output": None,
        "error": None,
        "duration_ms": run.duration_ms,
        "stdout": run.stdout_tail,
        "stderr": run.stderr_tail,
    }
    if run.status != "ok":
        return out
    report = run.report or {}
    entries = report.get("cases")
    if "fatal" in report or not isinstance(entries, list) or len(entries) != 1:
        out["status"] = "error"
        out["error"] = str(report.get("fatal") or "the harness did not write a report")
        return out
    entry = entries[0]
    if "error" in entry:
        out["error"] = str(entry["error"])
    else:
        text = json.dumps(entry.get("output"))
        out["output"] = (
            text if len(text) <= SHOWN_OUTPUT_CHARS else text[: SHOWN_OUTPUT_CHARS - 3] + "..."
        )
    return out


def submit(problem_id: str, language: str, code: str) -> dict[str, Any]:
    """Visible cases, then the hidden sample, each in its own sandbox. Counts only."""
    spec = spec_for(problem_id, language)
    files = _files(problem_id, language, code)
    visible = spec.dsa_cases.visible
    sample = dsa.hidden_sample(spec, HIDDEN_SEED_KEY)
    hidden = dsa.sampled_cases(spec, sample)
    total = len(visible) + len(hidden)

    first = dsa.run_cases(spec, files, visible, [c.id for c in visible])
    if first.status != "ok":
        return _submit_out(first.status, 0, total, first.duration_ms, "examples")
    if first.summary.failed:
        # Like LeetCode, stop at the first failing stage; hidden cases are not run.
        return _submit_out("ok", first.summary.passed, total, first.duration_ms, "examples")
    second = dsa.run_cases(spec, files, hidden, [c.id for c in hidden])
    duration = first.duration_ms + second.duration_ms
    if second.status != "ok":
        # The hidden run's output stays on the backend; only its status is reported.
        return _submit_out(second.status, first.summary.passed, total, duration, "hidden")
    passed = first.summary.passed + second.summary.passed
    stage = None if passed == total else "hidden"
    return _submit_out("ok", passed, total, duration, stage)


def _submit_out(
    status: str,
    passed: int,
    total: int,
    duration_ms: int,
    failed_stage: str | None,
) -> dict[str, Any]:
    """Pass counts and a status only: no case, no expected value, no program output."""
    return {
        "kind": "submit",
        "status": status,
        "accepted": status == "ok" and passed == total,
        "passed": passed,
        "total": total,
        "duration_ms": duration_ms,
        "failed_stage": failed_stage,
    }
