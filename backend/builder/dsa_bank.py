"""The DSA bank (P2.6): problems in dsa/<id>/, selection by tier and topics, task building.

Each bank folder holds problem.json (BankProblem), reference.py, cases.json, stub.py and
problem.md. Original descriptions (rewrite input only) live in the git-ignored dsa/raw/.
A task is built by renaming the problem into the candidate's domain (builder.dsa_rewrite),
writing the starter for the runtime, and checking the renamed reference in the sandbox.

About a third of the bank is practice-only (practice_split, `"practice_only": true` in
problem.json): practice mode shows only those, and select_problem never picks them, so a
candidate can't rehearse their assessment problem in practice.
"""

import hashlib
import json
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app import grading
from builder.seeds import DSA_DIR
from builder.tasks import BuiltTask, draft_certificate
from contracts_gen.profile import Profile
from contracts_gen.task_spec import DsaNames, NameMapping, TaskSpec
from profiler.taxonomy import TIERS

DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}
SOLUTION_FILE = {"python311": "solution.py", "node20": "solution.js"}
TIME_BUDGET_MIN = 25
EXAMPLES_SHOWN = 2
# Practice-only share of each difficulty, and problems that are always practice-only:
# `make e2e-practice` solves two_sum, tests/test_practice.py uses 3sum.
PRACTICE_SHARE = 1 / 3
PRACTICE_PINNED = frozenset({"two_sum", "3sum"})


class Param(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    """Python annotation over JSON types: int, float, bool, str, list[T], dict[str, T]."""


class Signature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    params: list[Param]
    returns: str


class BankComparator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["unordered_list", "float_tolerance"]
    tolerance: float | None


class BankProblem(BaseModel):
    """dsa/<id>/problem.json."""

    model_config = ConfigDict(extra="forbid")
    id: str
    difficulty: Literal["easy", "medium", "hard"]
    tiers: list[Literal["novice", "adept", "master"]] = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    """Canonical taxonomy topics (dsa/taxonomy.yaml)."""
    entry_point: str
    """Function name in reference.py and stub.py."""
    signature: Signature
    comparator: BankComparator | None
    own_statement: bool
    """problem.md is our own text (sent to the rewriter); else the description is in dsa/raw/."""
    source: dict[str, Any]
    practice_only: bool = False
    """Shown in practice mode only; never selected for an assessment (practice_split)."""

    @property
    def dir(self) -> Path:
        return DSA_DIR / self.id


@lru_cache
def load_bank(dsa_dir: Path = DSA_DIR) -> tuple[BankProblem, ...]:
    problems = [
        BankProblem.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(dsa_dir.glob("*/problem.json"))
    ]
    return tuple(sorted(problems, key=lambda p: p.id))


def load_cases(problem: BankProblem) -> dict[str, list[dict[str, Any]]]:
    return json.loads((problem.dir / "cases.json").read_text(encoding="utf-8"))


# --- Practice-only split --------------------------------------------------------------


def assessment_covers(bank: tuple[BankProblem, ...], practice: set[str]) -> bool:
    """Every (tier, problem) still has an assessment problem at that tier whose tags are a
    subset of the problem's, so no profile that fit a problem before loses all of them."""
    pool = [q for q in bank if q.id not in practice]
    return all(
        any(tier in q.tiers and set(q.tags) <= set(p.tags) for q in pool)
        for p in bank
        for tier in p.tiers
    )


def practice_split(bank: tuple[BankProblem, ...]) -> frozenset[str]:
    """The practice-only problem ids: PRACTICE_PINNED, then per difficulty, in sha256(id)
    order, until PRACTICE_SHARE of it is practice-only, skipping our own (hand-written)
    problems and any problem whose removal would break assessment_covers. Deterministic.
    """
    practice = {p.id for p in bank if p.id in PRACTICE_PINNED}
    if not assessment_covers(bank, practice):
        raise ValueError(f"pinned practice problems leave a profile without a problem: {practice}")
    for difficulty in DIFFICULTY_RANK:
        group = [p for p in bank if p.difficulty == difficulty]
        quota = round(len(group) * PRACTICE_SHARE)
        taken = sum(p.id in practice for p in group)
        for p in sorted(group, key=lambda p: hashlib.sha256(p.id.encode()).hexdigest()):
            if taken >= quota:
                break
            if p.id in practice or p.own_statement:
                continue
            if assessment_covers(bank, practice | {p.id}):
                practice.add(p.id)
                taken += 1
    return frozenset(practice)


def mark_practice_only(dsa_dir: Path = DSA_DIR) -> frozenset[str]:
    """Write practice_split into every dsa/<id>/problem.json (the key only where true)."""
    paths = sorted(dsa_dir.glob("*/problem.json"))
    bank = tuple(BankProblem.model_validate_json(p.read_text(encoding="utf-8")) for p in paths)
    practice = practice_split(bank)
    for path in paths:
        meta = json.loads(path.read_text(encoding="utf-8"))
        before = dict(meta)
        if meta["id"] in practice:
            meta["practice_only"] = True
        else:
            meta.pop("practice_only", None)
        if meta != before:
            path.write_bytes((json.dumps(meta, indent=1) + "\n").encode())
    return practice


# --- Selection ------------------------------------------------------------------------


class NoProblemError(LookupError):
    pass


@dataclass(frozen=True)
class Selection:
    problem: BankProblem
    tier: str
    """The tier the problem was picked for: the requested one, or a lower one (fallback)."""
    reason: str


def select_problem(
    profile: Profile, tier: str, rng_seed: int, bank: tuple[BankProblem, ...] | None = None
) -> Selection:
    """A problem for `tier` whose EVERY tag is in profile.allowed_topics[tier].

    If none qualify: the easiest problem whose tags are all allowed at some lower tier
    (and that is tagged for that tier). Raises NoProblemError when there is none either.
    Practice-only problems are never picked.
    """
    bank = tuple(p for p in (load_bank() if bank is None else bank) if not p.practice_only)
    allowed = _allowed(profile, tier)
    fits = [p for p in bank if tier in p.tiers and set(p.tags) <= allowed]
    if fits:
        problem = random.Random(rng_seed).choice(fits)
        reason = (
            f"{len(fits)} {tier} problems have every tag in allowed_topics.{tier}; "
            f"picked {problem.id} with seed {rng_seed}"
        )
        return Selection(problem, tier, reason)

    why = f"no {tier} problem has every tag in allowed_topics.{tier} ({_show(allowed)})"
    lower_fits = [
        (DIFFICULTY_RANK[p.difficulty], p.id, lower, p)
        for lower in TIERS[: TIERS.index(tier)]
        for p in bank
        if lower in p.tiers and set(p.tags) <= _allowed(profile, lower)
    ]
    if not lower_fits:
        raise NoProblemError(f"{why}, and none fits a lower tier")
    _, _, lower, problem = min(lower_fits)
    return Selection(problem, lower, f"{why}; fell back to the easiest {lower} problem")


def _allowed(profile: Profile, tier: str) -> set[str]:
    return {topic.root for topic in getattr(profile.allowed_topics, tier)}


def _show(topics: set[str]) -> str:
    return ", ".join(sorted(topics)) or "none"


# --- Names, stubs and statements ------------------------------------------------------


def identity_names(problem: BankProblem) -> DsaNames:
    return DsaNames(
        function=NameMapping(original=problem.entry_point, renamed=problem.entry_point),
        parameters=[NameMapping(original=p.name, renamed=p.name) for p in problem.signature.params],
    )


def renamed_signature(problem: BankProblem, names: DsaNames) -> list[tuple[str, str]]:
    """[(new parameter name, type)] in signature order."""
    new = {m.original: m.renamed for m in names.parameters}
    return [(new[p.name], p.type) for p in problem.signature.params]


def rename_input(value: Any, names: DsaNames) -> Any:
    if not isinstance(value, dict):
        return value
    new = {m.original: m.renamed for m in names.parameters}
    return {new[key]: item for key, item in value.items()}


def python_stub(problem: BankProblem, names: DsaNames) -> str:
    params = ", ".join(f"{n}: {t}" for n, t in renamed_signature(problem, names))
    return (
        f"def {names.function.renamed}({params}) -> {problem.signature.returns}:\n"
        "    # Your code here.\n"
        "    pass\n"
    )


def js_type(annotation: str) -> str:
    """Python annotation over JSON types -> JSDoc type."""
    annotation = annotation.replace(" ", "")
    if annotation.startswith("list[") and annotation.endswith("]"):
        inner = js_type(annotation[5:-1])
        return f"{inner}[]"
    if annotation.startswith("dict[str,") and annotation.endswith("]"):
        return f"Object<string, {js_type(annotation[9:-1])}>"
    return {"int": "number", "float": "number", "bool": "boolean", "str": "string"}[annotation]


def js_stub(problem: BankProblem, names: DsaNames) -> str:
    fn = names.function.renamed
    signature = renamed_signature(problem, names)
    doc = "".join(f" * @param {{{js_type(t)}}} {n}\n" for n, t in signature)
    doc += f" * @returns {{{js_type(problem.signature.returns)}}}\n"
    params = ", ".join(n for n, _ in signature)
    return (
        f"/**\n{doc} */\n"
        f"function {fn}({params}) {{\n"
        "  // Your code here.\n"
        "}\n\n"
        f"module.exports = {{ {fn} }};\n"
    )


def starter(problem: BankProblem, names: DsaNames, runtime: str) -> dict[str, str]:
    stub = python_stub if runtime == "python311" else js_stub
    return {SOLUTION_FILE[runtime]: stub(problem, names)}


def literal(value: Any, runtime: str) -> str:
    """A value as the candidate's language writes it."""
    if runtime == "node20":
        return json.dumps(value)
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(literal(v, runtime) for v in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ", ".join(f"{json.dumps(k)}: {literal(v, runtime)}" for k, v in value.items())
            + "}"
        )
    return repr(value)


def statement_md(
    problem: BankProblem,
    story: str,
    names: DsaNames,
    runtime: str,
    visible: list[dict[str, Any]],
) -> str:
    """The story plus code-built sections: the function to write and two worked examples."""
    fn = names.function.renamed
    signature = renamed_signature(problem, names)
    file = SOLUTION_FILE[runtime]
    if runtime == "python311":
        params = ", ".join(f"{n}: {t}" for n, t in signature)
        code = f"```python\ndef {fn}({params}) -> {problem.signature.returns}\n```"
        how = f"Write `{fn}` in `{file}`."
    else:
        code = f"```js\nfunction {fn}({', '.join(n for n, _ in signature)})\n```"
        how = f"Write `{fn}` in `{file}` and keep `module.exports = {{ {fn} }};`."
    parts = [story.strip(), "## Your function", f"{how}\n\n{code}", "## Examples"]
    for number, case in enumerate(visible[:EXAMPLES_SHOWN], start=1):
        args = ", ".join(f"{k} = {literal(v, runtime)}" for k, v in case["input"].items())
        parts.append(
            f"**Example {number}.** `{fn}({args})` returns `{literal(case['expected'], runtime)}`."
        )
    if problem.comparator and problem.comparator.kind == "unordered_list":
        parts.append("The returned list may be in any order.")
    elif problem.comparator and problem.comparator.kind == "float_tolerance":
        parts.append(f"Answers within {problem.comparator.tolerance} of the expected value count.")
    parts.append("Run checks the visible examples; Submit also runs hidden cases.")
    return "\n\n".join(parts) + "\n"


# --- Reference check and task building ------------------------------------------------


def wrapped_reference(problem: BankProblem, names: DsaNames) -> str:
    """reference.py plus a wrapper with the renamed function and parameters."""
    reference = (problem.dir / "reference.py").read_text(encoding="utf-8")
    new = [m.renamed for m in names.parameters]
    call = ", ".join(f"{m.original}={m.renamed}" for m in names.parameters)
    return (
        f"{reference.rstrip()}\n\n\n_bank_reference = {problem.entry_point}\n\n\n"
        f"def {names.function.renamed}({', '.join(new)}):\n"
        f"    return _bank_reference({call})\n"
    )


def task_spec(
    problem: BankProblem, story: str, names: DsaNames, runtime: str, tier: str
) -> dict[str, Any]:
    """The task spec, test ids filled in. Needs no Docker."""
    cases = load_cases(problem)

    def renamed(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [c | {"input": rename_input(c["input"], names)} for c in items]

    visible, hidden = renamed(cases["visible"]), renamed(cases["hidden"])
    entry = f"{SOLUTION_FILE[runtime]}::{names.function.renamed}"
    comparator = problem.comparator.model_dump() if problem.comparator else None
    spec = {
        "task_id": f"dsa-{problem.id.replace('_', '-')}",
        "version": 1,
        "tier": tier,
        "kind": "dsa",
        "mode": "seed",
        "seed_id": problem.id,
        "runtime": runtime,
        "dsa_tags": list(problem.tags),
        "statement_md": statement_md(problem, story, names, runtime, visible),
        "repo_tour_md": "",
        "starter_files": starter(problem, names, runtime),
        "reference_ref": f"dsa/{problem.id}/reference.py",
        "target_symbols": [entry],
        "entry_symbols": [entry],
        "visible_tests": [],
        "hidden_tests": [],
        "dsa_cases": {"visible": visible, "hidden": hidden, "comparator": comparator},
        "dsa_names": names.model_dump(),
        "perf": None,
        "time_budget_min": TIME_BUDGET_MIN,
        "random_seeds": [],
        "certificate": draft_certificate([SOLUTION_FILE[runtime]]),
        "ai_solve_rate": 0.0,
        "difficulty_index": 0.0,
    }
    return grading.derive_test_ids(spec)


Grade = Any  # Callable[[TaskSpec, dict[str, str]], grading.TaskGrade]


def reference_mismatch(problem: BankProblem, names: DsaNames, grade: Grade = None) -> str | None:
    """Run the reference behind the renamed wrapper on every case (Python sandbox).

    None when it passes all of them; else why not. JS tasks are checked the same way:
    expected values are computed on the backend, so the Python reference is the oracle.
    """
    grade = grade or grading.grade_task
    spec = TaskSpec.model_validate(task_spec(problem, "", names, "python311", problem.tiers[0]))
    result = grade(spec, {"solution.py": wrapped_reference(problem, names)})
    visible, hidden = len(result.visible_passed), len(result.hidden_passed)
    if visible == len(spec.visible_test_ids) and hidden == len(spec.hidden_test_ids):
        return None
    return (
        f"the renamed reference passed {visible}/{len(spec.visible_test_ids)} visible and "
        f"{hidden}/{len(spec.hidden_test_ids)} hidden cases"
    )


def build_dsa_task(
    problem: BankProblem,
    runtime: str,
    tier: str,
    domain: str,
    project_names: list[str],
    llm=None,
    grade: Grade = None,
) -> BuiltTask:
    """Rewrite `problem` into the domain and validate the task (needs Docker unless `grade`)."""
    from builder import dsa_rewrite

    grade = grade or grading.grade_task
    rewritten = dsa_rewrite.rewrite_problem(
        problem,
        domain,
        project_names,
        check=lambda names: reference_mismatch(problem, names, grade),
        **({"llm": llm} if llm is not None else {}),
    )
    if rewritten.source == "template":
        mismatch = reference_mismatch(problem, rewritten.names, grade)
        if mismatch is not None:
            raise ValueError(f"bank problem {problem.id} is broken: {mismatch}")
    spec = task_spec(problem, rewritten.story, rewritten.names, runtime, tier)
    task = TaskSpec.model_validate(spec)
    starter_grade = grade(task, {})
    starter_fails_visible = len(starter_grade.visible_passed) < len(task.visible_test_ids)
    starter_fails_hidden = len(starter_grade.hidden_passed) < len(task.hidden_test_ids)
    validation = {
        "task_id": task.task_id,
        "problem": problem.id,
        "statement": rewritten.source,
        "notes": rewritten.notes,
        "reference_passes_all": True,
        "starter_fails_visible": starter_fails_visible,
    }
    if not starter_fails_visible:
        raise ValueError(f"task {task.task_id} failed validation: {validation}")
    certificate = draft_certificate([SOLUTION_FILE[runtime]], True, starter_fails_hidden)
    spec = spec | {"certificate": certificate}
    return BuiltTask(
        spec=TaskSpec.model_validate(spec).model_dump(mode="json"), validation=validation
    )
