"""Feature removal for Adept tasks (P2.3): stub out one seed concept across 2-3 files.

The concept's functions (and its classes' non-dunder methods) keep their signature and
docstring; the body becomes `raise NotImplementedError("TODO: <first docstring line>")`.
Data-only classes and type aliases in the concept stay: they are the interface the
candidate codes against. Only concepts whose removed code spans 2-3 files are eligible.

Runner checks on the starter: the app imports, every test outside the concept still passes
(tests of concepts that call the removed code are exempt and become hidden tests), and the
concept's tests fail; on the seed they all pass. No LLM calls.

    python -m builder.remove_feature SEED [CONCEPT]
"""

import argparse
import ast
import difflib
import sys
from dataclasses import dataclass
from typing import Any

import libcst as cst

from app import grading
from builder.tasks import (
    STATEMENT_PLACEHOLDER,
    BuiltTask,
    concept_entry,
    draft_certificate,
    failing_functions,
    load_seed,
    split_concept_tests,
    starter_base,
    test_modules,
    validate_task,
)
from runner import run_tests

MIN_FILES, MAX_FILES = 2, 3
ADEPT_TIME_BUDGET_MIN = 40
IMPORT_CHECK = "tests/test_builder_import_check.py"


class FeatureRemovalError(ValueError):
    """The concept can't become an Adept task; the message says why and what would fix it."""


@dataclass(frozen=True)
class Checks:
    modules: list[str]
    imports_ok: bool
    other_tests: int
    other_failing: list[str]
    dependent_concepts: list[str]
    dependent_failing: list[str]
    target_tests: int
    target_failing_on_starter: list[str]
    target_failing_on_seed: list[str]


@dataclass(frozen=True)
class FeatureRemoval:
    built: BuiltTask
    targets: list[str]
    scope_files: list[str]
    diffs: dict[str, str]
    checks: Checks


# --- Targets and eligibility ----------------------------------------------------------


def _top_level(module: cst.Module, name: str) -> cst.CSTNode | None:
    for statement in module.body:
        if isinstance(statement, cst.FunctionDef | cst.ClassDef) and statement.name.value == name:
            return statement
    return None


def _methods(cls: cst.ClassDef) -> list[cst.FunctionDef]:
    return [
        node
        for node in cls.body.body
        if isinstance(node, cst.FunctionDef) and not node.name.value.startswith("__")
    ]


def concept_targets(files: dict[str, str], symbols: list[str]) -> list[str]:
    """The concept's code to remove, as "path::qualname": functions and non-dunder methods."""
    targets = []
    for ref in symbols:
        path, _, qualname = ref.partition("::")
        name, _, method = qualname.partition(".")
        node = _top_level(cst.parse_module(files[path]), name)
        if isinstance(node, cst.FunctionDef):
            targets.append(ref)
        elif isinstance(node, cst.ClassDef):
            targets += [
                f"{path}::{name}.{m.name.value}"
                for m in _methods(node)
                if not method or m.name.value == method
            ]
    return targets


def target_files(targets: list[str]) -> list[str]:
    return sorted({ref.split("::", 1)[0] for ref in targets})


def concept_spans(files: dict[str, str], concepts: dict[str, Any]) -> dict[str, list[str]]:
    """Concept -> files its removable code lives in."""
    return {
        name: target_files(concept_targets(files, entry["symbols"]))
        for name, entry in concepts["concepts"].items()
    }


def eligible(spans: dict[str, list[str]]) -> list[str]:
    return sorted(name for name, paths in spans.items() if MIN_FILES <= len(paths) <= MAX_FILES)


def suggest_seed_changes(spans: dict[str, list[str]]) -> list[str]:
    """What would make each concept eligible, for seeds where none is."""
    suggestions = []
    for name, paths in sorted(spans.items()):
        if not paths:
            suggestions.append(
                f"{name}: list at least two functions from different modules in concepts.yaml"
            )
        elif len(paths) < MIN_FILES:
            suggestions.append(
                f"{name}: all its code is in {paths[0]}; move one of its helpers into another "
                "module (e.g. a utils or repo function the main one calls) and list it under "
                f"{name} in concepts.yaml"
            )
        elif len(paths) > MAX_FILES:
            suggestions.append(
                f"{name}: spans {len(paths)} files; narrow its symbols in concepts.yaml to 2-3 "
                "of them"
            )
    return suggestions


# --- Stubbing -------------------------------------------------------------------------


def _docstring_statement(function: cst.FunctionDef) -> cst.BaseStatement | None:
    body = function.body
    first = body.body[0] if isinstance(body, cst.IndentedBlock) and body.body else None
    if (
        isinstance(first, cst.SimpleStatementLine)
        and len(first.body) == 1
        and isinstance(first.body[0], cst.Expr)
        and isinstance(first.body[0].value, cst.SimpleString | cst.ConcatenatedString)
    ):
        return first
    return None


def _string_literal(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def stub_function(function: cst.FunctionDef, qualname: str) -> cst.FunctionDef:
    """Keep the signature, decorators and docstring; the body raises NotImplementedError."""
    docstring = _docstring_statement(function)
    text = function.get_docstring()
    if docstring is None or not text:
        raise FeatureRemovalError(
            f"{qualname} has no docstring; add one to the seed (the stub's TODO uses its first "
            "line) and re-run the seed's tests"
        )
    first_line = next(line.strip() for line in text.splitlines() if line.strip())
    message = cst.SimpleString(_string_literal(f"TODO: {first_line}"))
    raise_line = cst.SimpleStatementLine(
        [cst.Raise(exc=cst.Call(func=cst.Name("NotImplementedError"), args=[cst.Arg(message)]))]
    )
    return function.with_changes(body=function.body.with_changes(body=[docstring, raise_line]))


def stub_module(source: str, qualnames: list[str]) -> str:
    module = cst.parse_module(source)
    for qualname in qualnames:
        name, _, method = qualname.partition(".")
        node = _top_level(module, name)
        if isinstance(node, cst.ClassDef) and method:
            old = next(m for m in _methods(node) if m.name.value == method)
        elif isinstance(node, cst.FunctionDef) and not method:
            old = node
        else:
            raise FeatureRemovalError(f"{qualname} is not a function or method")
        module = module.deep_replace(old, stub_function(old, qualname))
    return module.code


def stubbed_starter(files: dict[str, str], targets: list[str]) -> dict[str, str]:
    """The seed's starter with every target stubbed; only the target files differ."""
    starter = starter_base(files)
    for path in target_files(targets):
        qualnames = [ref.split("::", 1)[1] for ref in targets if ref.startswith(path + "::")]
        starter[path] = stub_module(starter[path], qualnames)
    return starter


# --- Dependencies between concepts ----------------------------------------------------


def _referenced_names(files: dict[str, str], symbols: list[str]) -> set[str]:
    names: set[str] = set()
    for ref in symbols:
        path, _, qualname = ref.partition("::")
        top = qualname.split(".")[0]
        for node in ast.parse(files[path]).body:
            defines = getattr(node, "name", None) == top or any(
                getattr(t, "id", None) == top for t in getattr(node, "targets", [])
            )
            if defines:
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Name):
                        names.add(inner.id)
                    elif isinstance(inner, ast.Attribute):
                        names.add(inner.attr)
    return names


def dependent_concepts(
    files: dict[str, str], concepts: dict[str, Any], concept: str, targets: list[str]
) -> list[str]:
    """Other concepts whose code calls the removed code, directly or through each other."""
    removed = {ref.split("::", 1)[1].split(".")[-1] for ref in targets}
    dependents: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, entry in concepts["concepts"].items():
            if name == concept or name in dependents:
                continue
            if _referenced_names(files, entry["symbols"]) & removed:
                dependents.add(name)
                removed |= {s.split("::", 1)[1].split(".")[-1] for s in entry["symbols"]}
                changed = True
    return sorted(dependents)


# --- Runner checks --------------------------------------------------------------------


def _module_names(starter: dict[str, str]) -> list[str]:
    modules = []
    for path in sorted(starter):
        if not path.endswith(".py") or path.startswith("tests/"):
            continue
        dotted = path.removesuffix(".py").replace("/", ".")
        modules.append(dotted.removesuffix(".__init__"))
    return modules


def _import_check(modules: list[str]) -> str:
    return (
        "import importlib\n\nimport pytest\n\n\n"
        f'@pytest.mark.parametrize("module", {modules!r})\n'
        "def test_imports(module):\n    importlib.import_module(module)\n"
    )


def check_removal(
    files: dict[str, str],
    concepts: dict[str, Any],
    concept: str,
    starter: dict[str, str],
    dependents: list[str],
) -> Checks:
    runtime = concepts["runtime"]
    tests = {path: files[path] for path in test_modules(files)}
    modules = _module_names(starter)
    check = {IMPORT_CHECK: _import_check(modules)}
    on_starter = run_tests(runtime, starter | tests | check, sorted(tests) + [IMPORT_CHECK], 120)
    if on_starter.status != "ok":
        raise FeatureRemovalError(
            f"the seed's tests could not run on the starter ({on_starter.status}): "
            f"{on_starter.stdout_tail[-500:]}"
        )
    on_seed = run_tests(runtime, starter_base(files) | tests, sorted(tests), 120)

    collected = {t.id.split("[", 1)[0] for t in on_starter.tests}
    failing = failing_functions(on_starter)
    target_tests = set(concept_entry(concepts, concept)["tests"])
    dependent_tests = {
        test for name in dependents for test in concept_entry(concepts, name)["tests"]
    }
    other = collected - target_tests - dependent_tests - {f"{IMPORT_CHECK}::test_imports"}
    return Checks(
        modules=modules,
        imports_ok=f"{IMPORT_CHECK}::test_imports" not in failing,
        other_tests=len(other),
        other_failing=sorted(failing & other),
        dependent_concepts=dependents,
        dependent_failing=sorted(failing & dependent_tests),
        target_tests=len(target_tests),
        target_failing_on_starter=sorted(failing & target_tests),
        target_failing_on_seed=sorted(failing_functions(on_seed) & target_tests),
    )


def _verdict(checks: Checks, concept: str) -> None:
    if not checks.imports_ok:
        raise FeatureRemovalError("the starter doesn't import after stubbing")
    if checks.other_failing:
        examples = ", ".join(checks.other_failing[:3])
        raise FeatureRemovalError(
            f"removing {concept} breaks {len(checks.other_failing)} tests of other concepts on "
            f"the starter (e.g. {examples}): its code is on a shared path"
        )
    if not checks.target_failing_on_starter:
        raise FeatureRemovalError(f"no {concept} test fails on the starter")
    if checks.target_failing_on_seed:
        raise FeatureRemovalError(f"{concept} tests fail on the seed itself")


# --- Draft task -----------------------------------------------------------------------


def remove_feature(seed_id: str, concept: str) -> FeatureRemoval:
    """A validated draft Adept task_spec with the concept's code stubbed out."""
    files, concepts = load_seed(seed_id)
    entry = concept_entry(concepts, concept)
    spans = concept_spans(files, concepts)
    if concept not in eligible(spans):
        options = ", ".join(eligible(spans)) or "none"
        raise FeatureRemovalError(
            f"{concept!r} is not eligible: its code spans {len(spans[concept])} file(s) "
            f"({', '.join(spans[concept]) or 'no functions'}), not {MIN_FILES}-{MAX_FILES}. "
            f"Eligible concepts in {seed_id}: {options}"
        )
    targets = concept_targets(files, entry["symbols"])
    scope = target_files(targets)
    starter = stubbed_starter(files, targets)
    dependents = dependent_concepts(files, concepts, concept, targets)
    checks = check_removal(files, concepts, concept, starter, dependents)
    _verdict(checks, concept)

    visible, hidden = split_concept_tests(
        files, entry["tests"], set(checks.target_failing_on_starter)
    )
    spec = {
        "task_id": f"{seed_id}-{concept}-adept",
        "version": 1,
        "tier": "adept",
        "kind": "domain",
        "mode": "seed",
        "seed_id": seed_id,
        "runtime": concepts["runtime"],
        "dsa_tags": [],
        "statement_md": STATEMENT_PLACEHOLDER.format(concept=concept),
        "repo_tour_md": files.get("README_TOUR.md", ""),
        "starter_files": starter,
        "reference_ref": f"seeds/{seed_id}",
        "target_symbols": targets,
        "entry_symbols": targets,
        "visible_tests": visible,
        "hidden_tests": hidden,
        "dsa_cases": None,
        "perf": None,
        "time_budget_min": ADEPT_TIME_BUDGET_MIN,
        "random_seeds": [],
        "certificate": draft_certificate(scope),
        "ai_solve_rate": 0.0,
        "difficulty_index": 0.0,
    }
    spec = grading.derive_test_ids(spec)
    built = validate_task(spec, {path: files[path] for path in scope}, scope)
    diffs = {
        path: "".join(
            difflib.unified_diff(
                files[path].splitlines(keepends=True),
                starter[path].splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=1,
            )
        )
        for path in scope
    }
    return FeatureRemoval(built, targets, scope, diffs, checks)


# --- CLI ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("seed")
    parser.add_argument("concept", nargs="?", default="")
    args = parser.parse_args(argv)

    files, concepts = load_seed(args.seed)
    spans = concept_spans(files, concepts)
    print(f"Concepts in {args.seed} (files holding the code to remove; eligible: 2-3):")
    for name, paths in sorted(spans.items()):
        mark = "eligible" if name in eligible(spans) else "not eligible"
        print(f"  {name:<11} {len(paths)} file(s)  {mark:<13} {', '.join(paths)}")
    if not eligible(spans):
        print("\nNo concept spans 2-3 files. Seed changes that would create one:")
        for line in suggest_seed_changes(spans):
            print(f"  - {line}")
    if not args.concept:
        return 0

    try:
        removal = remove_feature(args.seed, args.concept)
    except FeatureRemovalError as exc:
        print(f"\nCannot remove {args.concept}: {exc}")
        return 2
    checks, spec, validation = removal.checks, removal.built.spec, removal.built.validation
    print(
        f"\nRemoving {args.concept}: {len(removal.targets)} targets in "
        f"{len(removal.scope_files)} files"
    )
    for diff in removal.diffs.values():
        print(diff, end="")
    print("\nRunner checks:")
    print(f"  app imports: {'yes' if checks.imports_ok else 'NO'} ({', '.join(checks.modules)})")
    print(
        f"  tests of other concepts pass on the starter: "
        f"{checks.other_tests - len(checks.other_failing)}/{checks.other_tests}"
    )
    if checks.dependent_concepts:
        print(
            f"  concepts that call the removed code ({', '.join(checks.dependent_concepts)}): "
            f"{len(checks.dependent_failing)} of their tests fail on the starter; all hidden"
        )
    print(
        f"  {args.concept} tests failing on the starter: "
        f"{len(checks.target_failing_on_starter)}/{checks.target_tests}; "
        f"on the seed: {len(checks.target_failing_on_seed)}/{checks.target_tests}"
    )
    print(f"\nDraft task {spec['task_id']} (tier {spec['tier']}, mode {spec['mode']}):")
    print(f"  scope_files: {spec['certificate']['scope_files']}")
    print(f"  visible tests ({len(spec['visible_test_ids'])}): {spec['visible_test_ids']}")
    print(
        f"  hidden tests: {len(spec['hidden_test_ids'])} in "
        f"{sorted({i.split('::')[0] for i in spec['hidden_test_ids']})}"
    )
    print(f"  validation: starter {validation['starter']}, reference {validation['reference']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
