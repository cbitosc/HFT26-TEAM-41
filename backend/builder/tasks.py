"""Shared pieces of the domain task builders (manual.py, mutate.py, remove_feature.py):
seed concepts, starter files, the visible/hidden test split, certificates, validation.
"""

import ast
from dataclasses import dataclass
from typing import Any

import yaml

from app import grading
from builder.perf import PERF_DIR
from builder.seeds import SEEDS_DIR, seed_files
from contracts_gen.run_result import RunResult
from contracts_gen.task_spec import TaskSpec

# Seed files that are not part of a candidate's repo: the tour becomes repo_tour_md.
NOT_IN_STARTER = {"concepts.yaml", "README_TOUR.md"}
STATEMENT_PLACEHOLDER = (
    "TODO(P2.5): the statement is written by LLM enrichment. Concept: {concept}."
)


@dataclass(frozen=True)
class BuiltTask:
    spec: dict[str, Any]
    validation: dict[str, Any]


# --- Seeds ----------------------------------------------------------------------------


def load_seed(seed_id: str) -> tuple[dict[str, str], dict[str, Any]]:
    """(every file of the seed, its parsed concepts.yaml)."""
    seed_dir = SEEDS_DIR / seed_id
    if not (seed_dir / "concepts.yaml").is_file():
        raise ValueError(f"unknown seed {seed_id!r}")
    files = seed_files(seed_dir)
    return files, yaml.safe_load(files["concepts.yaml"])


def concept_entry(concepts: dict[str, Any], concept: str) -> dict[str, Any]:
    entry = concepts["concepts"].get(concept)
    if entry is None:
        known = ", ".join(sorted(concepts["concepts"]))
        raise ValueError(f"unknown concept {concept!r}; this seed has: {known}")
    return entry


def is_test_module(path: str) -> bool:
    return path.startswith("tests/test_") and path.endswith(".py")


def starter_base(files: dict[str, str]) -> dict[str, str]:
    """The seed as a candidate sees it before any change: app code and config, no test modules."""
    return {
        p: c
        for p, c in files.items()
        if not is_test_module(p) and p not in NOT_IN_STARTER and not p.startswith(PERF_DIR)
    }


def test_modules(files: dict[str, str]) -> list[str]:
    return sorted(p for p in files if is_test_module(p))


def failing_functions(result: RunResult) -> set[str]:
    """Every test that didn't pass, as path::function (parametrized cases collapsed)."""
    return {_function_ref(t.id) for t in result.tests if t.outcome != "passed"}


def _function_ref(test_id: str) -> str:
    path, _, name = test_id.partition("::")
    return f"{path}::{name.split('[', 1)[0]}"


# --- Test splitting -------------------------------------------------------------------


def collect_test_names(source: str) -> list[str]:
    """Top-level test functions, in source order."""
    return [
        node.name
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    ]


def split_test_module(source: str, selected: set[str]) -> tuple[str, str]:
    """(module with the `selected` tests, module with the other tests).

    Both keep every non-test statement (imports, fixtures, helpers) in source order.
    """
    names = collect_test_names(source)
    if unknown := selected - set(names):
        raise ValueError(f"unknown tests: {sorted(unknown)}")
    lines = source.splitlines()
    header: list[tuple[ast.stmt, str]] = []
    tests: list[tuple[str, str]] = []
    for node in ast.parse(source).body:
        first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        text = "\n".join(lines[first - 1 : node.end_lineno])
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in names:
            tests.append((node.name, text))
        else:
            header.append((node, text))

    def module(keep: set[str]) -> str:
        parts: list[str] = []
        previous: ast.stmt | None = None
        for node, text in header:
            imports = (ast.Import, ast.ImportFrom)
            joined = (
                previous is not None and isinstance(previous, imports) and isinstance(node, imports)
            )
            parts.append(("\n" if joined else "\n\n\n" if parts else "") + text)
            previous = node
        parts += ["\n\n\n" + text for name, text in tests if name in keep]
        return "".join(parts) + "\n"

    return module(selected), module(set(names) - selected)


def choose_visible(names: list[str], failing: set[str]) -> list[str]:
    """About a third of `names`: the first failing test, then passing ones, in source order."""
    if not failing & set(names):
        raise ValueError("the starter must fail at least one test")
    count = max(1, round(len(names) / 3))
    first_failing = next(n for n in names if n in failing)
    passing = [n for n in names if n not in failing]
    return [n for n in names if n == first_failing or n in passing[: count - 1]]


def hidden_path(path: str) -> str:
    return path.removesuffix(".py") + "_hidden.py"


def split_concept_tests(
    files: dict[str, str], concept_tests: list[str], failing: set[str]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """(visible TestFiles, hidden TestFiles) for a task on one concept.

    About a third of the concept's tests are visible, including one that fails on the
    starter. Each module holding visible tests is split: visible tests keep its path, the
    rest go to `<module>_hidden.py`. Every other test module is hidden unchanged.
    """
    visible_refs = set(choose_visible(concept_tests, failing))
    visible, hidden = [], []
    for path in test_modules(files):
        selected = {ref.split("::", 1)[1] for ref in visible_refs if ref.startswith(path + "::")}
        if not selected:
            hidden.append({"path": path, "content": files[path]})
            continue
        visible_source, hidden_source = split_test_module(files[path], selected)
        visible.append({"path": path, "content": visible_source})
        if collect_test_names(hidden_source):
            hidden.append({"path": hidden_path(path), "content": hidden_source})
    return visible, sorted(hidden, key=lambda test: test["path"])


# --- Specs and validation -------------------------------------------------------------


def draft_certificate(
    scope_files: list[str], reference_pass: bool = False, starter_fail: bool = False
) -> dict[str, Any]:
    # A draft: the validation gate (backend/gate, P2.7) replaces it with the real certificate.
    return {
        "reference_pass": reference_pass,
        "starter_fail": starter_fail,
        "mutation_score": None,
        "perf_ref_ms": None,
        "perf_naive_ms": None,
        "scope_files": scope_files,
    }


def validate_task(
    spec: dict[str, Any], reference_files: dict[str, str], scope_files: list[str]
) -> BuiltTask:
    """Grade the starter and the reference in the sandbox; refuse a task that isn't sound."""
    task = TaskSpec.model_validate(spec)
    starter = grading.grade_task(task, {})
    reference = grading.grade_task(task, reference_files)

    def counts(grade: grading.TaskGrade) -> dict[str, Any]:
        return {
            "visible": f"{len(grade.visible_passed)}/{len(task.visible_test_ids)}",
            "hidden": f"{len(grade.hidden_passed)}/{len(task.hidden_test_ids)}",
        }

    starter_fails_visible = len(starter.visible_passed) < len(task.visible_test_ids)
    starter_fails_hidden = len(starter.hidden_passed) < len(task.hidden_test_ids)
    reference_passes_all = len(reference.visible_passed) == len(task.visible_test_ids) and len(
        reference.hidden_passed
    ) == len(task.hidden_test_ids)
    validation = {
        "task_id": task.task_id,
        "starter": counts(starter),
        "reference": counts(reference),
        "starter_fails_visible": starter_fails_visible,
        "reference_passes_all": reference_passes_all,
    }
    if not (starter_fails_visible and reference_passes_all):
        raise ValueError(f"task {task.task_id} failed validation: {validation}")
    spec = spec | {
        "certificate": draft_certificate(scope_files, reference_passes_all, starter_fails_hidden)
    }
    return BuiltTask(
        spec=TaskSpec.model_validate(spec).model_dump(mode="json"), validation=validation
    )
