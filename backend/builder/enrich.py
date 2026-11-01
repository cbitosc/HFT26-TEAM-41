"""LLM enrichment of draft domain tasks (P2.5): statement, repo tour, entity renaming.

One generator call per task (llm.complete_structured, cached by input hash in
backend/llm, max_tokens 500, temperature 0.2; tokens are logged per call, see
`make llm-usage`) returns an issue-style statement and a rename map. The model sees only
the starter side of the diff (never reference code, CLAUDE.md rule 2), the target
symbols, the visible failing tests with the last lines of their messages, the tier, and
the candidate's project names.

Plain code then: rejects a statement that leaks the fix (retry once, then a template),
appends the perf budget for Master, copies the seed's repo tour, and applies the rename map
with LibCST. A renamed task is re-derived and re-run (reference and starter); if any test
result differs from the original, the renaming is dropped.

The P1.3 demo tasks (builder/manual.py) are never enriched, so `make e2e` is unchanged.

    python -m builder.enrich SEED --tier novice|adept [--concept C] [--portfolio PATH]
"""

import argparse
import difflib
import json
import keyword
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import libcst as cst
from pydantic import BaseModel, Field

from app import grading
from builder.manual import DEMO_TASK_IDS
from builder.master import perf_budget_sentence
from builder.tasks import load_seed, split_test_module, starter_base
from contracts_gen.task_spec import TaskSpec
from gate import leak
from llm import complete_structured
from llm.client import summarize_error
from runner import run_tests

STATEMENT_MAX_TOKENS = 500
STATEMENT_TEMPERATURE = 0.2
EXTRA_TESTS_MAX_TOKENS = 1200
MESSAGE_LINES = 20
EXTRA_TESTS_PATH = "tests/test_extra_hidden.py"
RENAMED_WORD = re.compile(r"^[a-z]{3,20}$")

SYSTEM_PROMPT = """\
You write the statement of a coding-assessment task, like a GitHub issue from a teammate.
Describe the symptoms (what goes wrong, with an example from the failing tests) and the
expected behaviour. Never say how to fix it: no code, operators, constants or lines from a
fix, and no "change X to Y". Plain Markdown, at most 200 words, no headings.
Also return `renames`: map each of `renamable_terms` that has a natural counterpart in one
of the candidate's projects to one lowercase singular English noun from that project's
domain (e.g. expense -> order, category -> department for a shop). Leave out terms
without a natural counterpart; return {} only if no project suggests any. Write the
statement with the original terms; renaming is applied afterwards by code."""


class Enrichment(BaseModel):
    title: str = Field(max_length=100)
    statement: str
    renames: dict[str, str] = Field(default_factory=dict)


Llm = Callable[..., BaseModel]
"""llm.complete_structured: (slot, messages, response_model, temperature=, max_tokens=)."""


@dataclass
class Enriched:
    spec: dict[str, Any]
    statement_source: str = "llm"
    """llm, llm_retry or template."""
    rejections: list[str] = field(default_factory=list)
    renames: dict[str, str] = field(default_factory=dict)
    rename_status: str = "none"
    notes: list[str] = field(default_factory=list)
    """LLM failures (budget, API errors); each falls back to code."""


# --- Diff and leak check --------------------------------------------------------------


@dataclass(frozen=True)
class FixInfo:
    starter_diff: str
    """Unified diff reference -> starter with the reference side (`-` lines) removed."""
    reference_lines: list[str]
    fragments: list[str]


def fix_info(reference: dict[str, str], starter: dict[str, str]) -> FixInfo:
    """What the model may see (starter side) and what the statement must not contain.

    The leak evidence comes from backend/gate/leak.py, the check the gate certifies with.
    """
    diff_parts = []
    for path in sorted(reference):
        before = reference[path].splitlines()
        after = starter[path].splitlines()
        diff = difflib.unified_diff(before, after, f"a/{path}", f"b/{path}", n=2, lineterm="")
        diff_parts += [line for line in diff if not line.startswith("-") or line.startswith("---")]
    reference_lines, fragments = leak.fix_evidence(reference, starter)
    return FixInfo("\n".join(diff_parts), reference_lines, fragments)


# --- Statement ------------------------------------------------------------------------


def _failing_visible(spec: dict[str, Any]) -> list[dict[str, str]]:
    """Visible tests failing on the starter, with the last lines of their messages."""
    result = grading.run_visible(TaskSpec.model_validate(spec), {})
    return [
        {
            "test": t.id,
            "message": "\n".join((t.message or "").splitlines()[-MESSAGE_LINES:]),
        }
        for t in result.tests
        if t.outcome != "passed"
    ]


def _kind(spec: dict[str, Any]) -> str:
    return {
        "novice": "bug fix",
        "adept": "missing feature: the stubbed functions raise NotImplementedError",
        "master": "bug fix; part of the code is also too slow (the budget is added separately)",
    }[spec["tier"]]


def statement_messages(
    spec: dict[str, Any],
    info: FixInfo,
    failing: list[dict[str, str]],
    project_names: list[str],
    renamable: list[str],
) -> list[dict[str, str]]:
    # The tour's first paragraph says what the app is about, so the renames can fit it.
    summary = next(
        (p.strip() for p in spec["repo_tour_md"].split("\n\n") if p.strip()[:1] not in "#-"),
        "",
    )
    context = {
        "repo_summary": summary,
        "tier": spec["tier"],
        "task": _kind(spec),
        "target_symbols": spec["target_symbols"],
        "starter_diff": info.starter_diff,
        "visible_failing_tests": failing,
        "candidate_projects": project_names,
        "renamable_terms": renamable,
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(context, indent=1)},
    ]


def template_statement(spec: dict[str, Any], failing: list[dict[str, str]]) -> tuple[str, str]:
    """(title, body) built by code, used when the model's statements leak twice."""
    symbols = ", ".join(f"`{s.split('::', 1)[1]}`" for s in spec["target_symbols"])
    if spec["tier"] == "adept":
        title = "Finish a missing feature"
        intro = f"These functions are not implemented yet: {symbols}."
    else:
        title = "Fix a reported bug"
        intro = "Users report wrong results from the code around " + symbols + "."
    checks = [
        f"- `{f['test'].split('::', 1)[1]}`: "
        + (f["message"].strip().splitlines() or ["fails"])[-1][:160]
        for f in failing
    ]
    body = (
        f"{intro}\n\nThese checks fail on the current code:\n"
        + "\n".join(checks)
        + "\n\nExpected: the visible tests pass, and the behaviour they describe holds for "
        "every input (more tests run when you submit)."
    )
    return title, body


# --- Renaming -------------------------------------------------------------------------


def _plural(word: str) -> str:
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "ch", "sh")):
        return word + "es"
    return word + "s"


def _forms(old: str, new: str) -> list[tuple[re.Pattern[str], str]]:
    pairs = []
    for a, b in ((_plural(old), _plural(new)), (old, new)):  # plural first
        for case in (str.lower, str.capitalize, str.upper):
            pairs.append((re.compile(rf"(?<![A-Za-z]){case(a)}(?![a-z])"), case(b)))
    return pairs


def rename_text(text: str, renames: dict[str, str]) -> str:
    """Rename whole word parts: `expense`, `Expense`, `expenses_of`, `ExpenseCreate`."""
    for old, new in renames.items():
        for pattern, replacement in _forms(old, new):
            text = pattern.sub(replacement, text)
    return text


class _Renamer(cst.CSTTransformer):
    def __init__(self, renames: dict[str, str]) -> None:
        self.renames = renames

    def leave_Name(self, original: cst.Name, updated: cst.Name) -> cst.Name:
        return updated.with_changes(value=rename_text(updated.value, self.renames))

    def leave_SimpleString(
        self, original: cst.SimpleString, updated: cst.SimpleString
    ) -> cst.SimpleString:
        return updated.with_changes(value=rename_text(updated.value, self.renames))

    def leave_FormattedStringText(
        self, original: cst.FormattedStringText, updated: cst.FormattedStringText
    ) -> cst.FormattedStringText:
        return updated.with_changes(value=rename_text(updated.value, self.renames))

    def leave_Comment(self, original: cst.Comment, updated: cst.Comment) -> cst.Comment:
        return updated.with_changes(value=rename_text(updated.value, self.renames))


def rename_source(path: str, source: str, renames: dict[str, str]) -> str:
    if not renames:
        return source
    if path.endswith(".py"):
        return cst.parse_module(source).visit(_Renamer(renames)).code
    return rename_text(source, renames)


def _identifiers(files: dict[str, str]) -> set[str]:
    return {
        node.value
        for path, source in files.items()
        if path.endswith(".py")
        for node in _all_names(cst.parse_module(source))
    }


def _all_names(module: cst.Module) -> list[cst.Name]:
    found: list[cst.Name] = []

    class Collect(cst.CSTVisitor):
        def visit_Name(self, node: cst.Name) -> None:
            found.append(node)

    module.visit(Collect())
    return found


def valid_renames(
    proposed: dict[str, str], renamable: list[str], files: dict[str, str]
) -> tuple[dict[str, str], list[str]]:
    """(the usable part of the model's map, why the rest was dropped)."""
    names = _identifiers(files)
    renames, dropped = {}, []
    for old, new in proposed.items():
        new = new.strip().lower()
        if old not in renamable:
            dropped.append(f"{old}: not a renamable term")
        elif new == old:
            continue
        elif not RENAMED_WORD.match(new) or keyword.iskeyword(new) or new in renamable:
            dropped.append(f"{old} -> {new}: not a plain new noun")
        elif new in renames.values():
            dropped.append(f"{old} -> {new}: used twice")
        else:
            renames[old] = new
    # A renamed identifier must not become one that already exists (e.g. `sort`).
    for old, new in list(renames.items()):
        clashes = {
            rename_text(name, {old: new}) for name in names if rename_text(name, {old: new}) != name
        } & names
        if clashes:
            dropped.append(f"{old} -> {new}: clashes with {sorted(clashes)}")
            del renames[old]
    return renames, dropped


def renamed_spec(spec: dict[str, Any], renames: dict[str, str]) -> dict[str, Any]:
    """The spec with code, tests, symbols, tour and statement renamed; test ids not derived."""

    def tests(files: list[dict[str, str]]) -> list[dict[str, str]]:
        return [t | {"content": rename_source(t["path"], t["content"], renames)} for t in files]

    pairs = ",".join(f"{old}:{new}" for old, new in sorted(renames.items()))
    return spec | {
        "starter_files": {
            p: rename_source(p, c, renames) for p, c in spec["starter_files"].items()
        },
        "visible_tests": tests(spec["visible_tests"]),
        "hidden_tests": tests(spec["hidden_tests"]),
        "target_symbols": [rename_text(s, renames) for s in spec["target_symbols"]],
        "entry_symbols": [rename_text(s, renames) for s in spec["entry_symbols"]],
        "repo_tour_md": rename_text(spec["repo_tour_md"], renames),
        "statement_md": rename_text(spec["statement_md"], renames),
        "reference_ref": spec["reference_ref"].split("?", 1)[0] + f"?rename={pairs}",
        "visible_test_ids": [],
        "hidden_test_ids": [],
    }


def reference_files(spec: dict[str, Any]) -> dict[str, str]:
    """The reference version of the task's scope files, renamed like the task."""
    base, _, query = spec["reference_ref"].partition("?rename=")
    files, _ = load_seed(base.removeprefix("seeds/"))
    renames = dict(pair.split(":", 1) for pair in query.split(",") if pair)
    return {
        path: rename_source(path, files[path], renames)
        for path in spec["certificate"]["scope_files"]
    }


def _outcomes(spec: dict[str, Any]) -> dict[str, dict[str, str]]:
    task = TaskSpec.model_validate(spec)
    results = {}
    for name, files in (("starter", {}), ("reference", reference_files(spec))):
        grade = grading.grade_task(task, files)
        for kind, run in (("visible", grade.visible), ("hidden", grade.hidden)):
            results[f"{name}.{kind}"] = {t.id: t.outcome for t in run.tests} | {
                "(status)": run.status
            }
    return results


def sandbox_rename_check(
    original: dict[str, Any], renamed: dict[str, Any], renames: dict[str, str]
) -> tuple[dict[str, Any] | None, str]:
    """(renamed spec with test ids, "applied"), or (None, why) when any result differs."""
    try:
        renamed = grading.derive_test_ids(renamed)
    except ValueError as exc:
        return None, f"dropped: renamed tests don't run ({exc})"
    before, after = _outcomes(original), _outcomes(renamed)
    expected = {
        run: {rename_text(test, renames): outcome for test, outcome in outcomes.items()}
        for run, outcomes in before.items()
    }
    if expected != after:
        differing = sorted(run for run in after if after[run] != expected[run])
        return None, f"dropped: results differ after renaming ({', '.join(differing)})"
    return renamed, "applied"


# --- Extra hidden tests (flag, off by default) ----------------------------------------


class ExtraTests(BaseModel):
    module: str
    """A pytest module of new test functions."""


def extra_hidden_tests(
    spec: dict[str, Any], llm: Llm = complete_structured, run: Callable[..., Any] = run_tests
) -> tuple[dict[str, Any], int]:
    """(spec with the reference-passing LLM tests added as hidden, how many were kept)."""
    targets = sorted({s.split("::")[0] for s in spec["target_symbols"]})
    context = {
        "statement": spec["statement_md"],
        "target_code": {path: spec["starter_files"][path] for path in targets},
        "visible_tests": spec["visible_tests"],
    }
    messages = [
        {
            "role": "system",
            "content": "Write extra pytest test functions (module source, same imports and "
            "fixtures as the visible tests) that check the behaviour the statement asks for. "
            "The code shown may contain the bug; test the intended behaviour.",
        },
        {"role": "user", "content": json.dumps(context, indent=1)},
    ]
    try:
        answer = llm(
            "generator",
            messages,
            ExtraTests,
            temperature=STATEMENT_TEMPERATURE,
            max_tokens=EXTRA_TESTS_MAX_TOKENS,
        )
        compile(answer.module, EXTRA_TESTS_PATH, "exec")
    except Exception:  # noqa: BLE001 - extra tests are optional; any failure adds none
        return spec, 0
    workspace = (
        spec["starter_files"]
        | reference_files(spec)
        | {t["path"]: t["content"] for t in spec["visible_tests"]}
        | {EXTRA_TESTS_PATH: answer.module}
    )
    result = run(spec["runtime"], workspace, [EXTRA_TESTS_PATH], 120)
    passing = {
        t.id.split("::", 1)[1].split("[", 1)[0]
        for t in result.tests
        if result.status == "ok" and t.outcome == "passed"
    }
    failing = {t.id.split("::", 1)[1].split("[", 1)[0] for t in result.tests} - passing
    kept = passing - failing  # a parametrized test is kept only if every case passes
    if not kept:
        return spec, 0
    module, _ = split_test_module(answer.module, kept)
    hidden = spec["hidden_tests"] + [{"path": EXTRA_TESTS_PATH, "content": module}]
    return grading.derive_test_ids(spec | {"hidden_tests": hidden}), len(kept)


# --- Enrich ---------------------------------------------------------------------------


def enrich(
    draft_spec: dict[str, Any],
    profile: dict[str, Any] | None,
    project_names: list[str],
    llm: Llm = complete_structured,
    failing_visible: Callable[[dict[str, Any]], list[dict[str, str]]] = _failing_visible,
    rename_check: Callable[..., tuple[dict[str, Any] | None, str]] = sandbox_rename_check,
    extra_tests: bool = False,
    extra_llm: Llm = complete_structured,
) -> Enriched:
    """`draft_spec` with a statement, the repo tour and (when safe) renamed entities.

    `profile` (the candidate's Profile) is not sent to the model: the tier comes from the
    spec and the projects from `project_names` (the portfolio's project names).
    """
    if draft_spec["task_id"] in DEMO_TASK_IDS or draft_spec["kind"] != "domain":
        return Enriched(spec=draft_spec, statement_source="unchanged")
    files, concepts = load_seed(draft_spec["seed_id"])
    renamable = list(concepts.get("renamable", []))
    scope = draft_spec["certificate"]["scope_files"]
    info = fix_info({p: files[p] for p in scope}, draft_spec["starter_files"])
    failing = failing_visible(draft_spec)
    result = Enriched(spec=draft_spec)

    messages = statement_messages(draft_spec, info, failing, project_names, renamable)
    answer = first = None
    for attempt in (1, 2):
        try:
            candidate = llm(
                "generator",
                messages,
                Enrichment,
                temperature=STATEMENT_TEMPERATURE,
                max_tokens=STATEMENT_MAX_TOKENS,
            )
        except Exception as exc:  # noqa: BLE001 - any LLM failure falls back to the template
            result.notes.append(f"statement attempt {attempt} failed: {summarize_error(exc)}")
            break
        reasons = leak.statement_problems(
            f"{candidate.title}\n{candidate.statement}", info.reference_lines, info.fragments
        )
        if not reasons:
            answer = candidate
            result.statement_source = "llm" if attempt == 1 else "llm_retry"
            break
        result.rejections += reasons
        first = first or candidate  # its rename map is still usable
        # A different conversation, so the retry isn't answered from the cache.
        messages = messages + [
            {"role": "assistant", "content": candidate.model_dump_json()},
            {
                "role": "user",
                "content": f"Rejected: {'; '.join(reasons)}. Describe only symptoms and "
                "expected behaviour, without the fix.",
            },
        ]
    if answer is None:
        title, body = template_statement(draft_spec, failing)
        proposed = first.renames if first else {}
        result.statement_source = "template"
    else:
        title, body, proposed = answer.title, answer.statement, answer.renames

    statement = f"### {title.strip()}\n\n{body.strip()}"
    if draft_spec["tier"] == "master":
        statement += "\n\n" + perf_budget_sentence(draft_spec)
    spec = draft_spec | {
        "statement_md": statement,
        "repo_tour_md": files.get("README_TOUR.md", ""),
    }

    renames, dropped = valid_renames(proposed, renamable, starter_base(files))
    result.spec = spec
    if dropped:
        result.rename_status = "partly dropped: " + "; ".join(dropped)
    if renames:
        checked, status = rename_check(spec, renamed_spec(spec, renames), renames)
        result.rename_status = status
        if checked is not None:
            result.spec, result.renames = checked, renames

    if extra_tests:
        result.spec, kept = extra_hidden_tests(result.spec, extra_llm)
        result.notes.append(f"extra hidden tests kept: {kept}")
    return result


# --- CLI ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    from builder.mutate import draft_novice_task, inject_bug, prefilter, ranked
    from builder.remove_feature import remove_feature
    from builder.seeds import REPO_ROOT
    from profiler.profile import build_profile

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("seed")
    parser.add_argument("--tier", choices=["novice", "adept"], required=True)
    parser.add_argument("--concept", default="")
    parser.add_argument("--rng-seed", type=int, default=0)
    parser.add_argument(
        "--portfolio", default=str(REPO_ROOT / "contracts/fixtures/portfolio.valid.json")
    )
    parser.add_argument("--extra-tests", action="store_true")
    args = parser.parse_args(argv)

    with open(args.portfolio, encoding="utf-8") as handle:
        portfolio = json.load(handle)
    projects = [p["name"] for p in portfolio.get("projects", []) if p.get("name")]
    if args.tier == "novice":
        concept = args.concept or "pagination"
        checked = prefilter(args.seed, concept, inject_bug(args.seed, concept, args.rng_seed))
        draft = draft_novice_task(args.seed, concept, ranked(checked)[0], args.rng_seed).spec
    else:
        draft = remove_feature(args.seed, args.concept or "reporting").built.spec

    enriched = enrich(
        draft, build_profile(portfolio).model_dump(), projects, extra_tests=args.extra_tests
    )
    spec = enriched.spec
    print(f"Task {spec['task_id']} (tier {spec['tier']}); candidate projects: {projects}")
    print(f"statement source: {enriched.statement_source}")
    for reason in enriched.rejections:
        print(f"  rejected: {reason}")
    print(f"rename map: {enriched.renames or '{}'} ({enriched.rename_status})")
    print(f"target_symbols: {spec['target_symbols']}")
    print(f"reference_ref: {spec['reference_ref']}")
    for note in enriched.notes:
        print(f"  note: {note}")
    print("\n" + spec["statement_md"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
