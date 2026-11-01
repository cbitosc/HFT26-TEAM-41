"""Mutation engine for Novice tasks (P2.2): inject one realistic bug into a seed concept.

inject_bug() enumerates every site where an operator applies inside the concept's symbols
(seeds/<seed>/concepts.yaml) and orders the candidates by rng_seed. prefilter() runs the
seed's tests on candidates in the sandbox and keeps the ones that make a good task.
draft_novice_task() turns the best one into a validated draft task_spec.

Operators edit LibCST trees, so everything outside the changed node keeps its formatting.
No LLM calls.

    python -m builder.mutate SEED CONCEPT [--rng-seed N] [--max-runs N] [--no-draft]
"""

import argparse
import difflib
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import libcst as cst
from libcst.metadata import MetadataWrapper, ParentNodeProvider, PositionProvider

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

MAX_RUNS = 12
MAX_FAILING_SHARE = 0.4
PREFERRED_FAILING = range(1, 6)  # 1-5 failing tests
NOVICE_TIME_BUDGET_MIN = 35


@dataclass(frozen=True)
class Site:
    """One applicable edit: replace `old` with `new` (None removes the statement)."""

    operator: str
    old: cst.CSTNode
    new: cst.CSTNode | None
    description: str
    anchor: cst.CSTNode | None = None  # the node whose line is reported, if not `old`


@dataclass(frozen=True)
class Mutation:
    operator: str
    qualname: str
    line: int
    description: str
    source: str


@dataclass(frozen=True)
class Candidate:
    operator: str
    file: str
    line: int
    description: str
    target_symbols: list[str]
    starter_files: dict[str, str]
    diff: str
    changed_line: str


@dataclass(frozen=True)
class Checked:
    candidate: Candidate
    kept: bool
    reason: str
    failing: int = 0
    total: int = 0
    failing_tests: frozenset[str] = field(default_factory=frozenset)


# --- Operators ------------------------------------------------------------------------
# Each takes the code of one symbol and yields Sites. `context` gives code_for_node and the
# parent of a node; `types` maps the enclosing function's parameter names to annotations.


@dataclass(frozen=True)
class Context:
    module: cst.Module
    parents: dict[cst.CSTNode, cst.CSTNode]
    types: dict[str, str]

    def code(self, node: cst.CSTNode) -> str:
        return " ".join(self.module.code_for_node(node).split())


def _nodes(scope: cst.CSTNode, kind: type) -> Iterator:
    found: list = []

    class Collect(cst.CSTVisitor):
        def on_visit(self, node: cst.CSTNode) -> bool:
            if isinstance(node, kind):
                found.append(node)
            return True

    scope.visit(Collect())
    yield from found


# Comparison operator -> (its flip, source text of the original).
_FLIPS: dict[type, tuple[type, str]] = {
    cst.LessThan: (cst.LessThanEqual, "<"),
    cst.LessThanEqual: (cst.LessThan, "<="),
    cst.GreaterThan: (cst.GreaterThanEqual, ">"),
    cst.GreaterThanEqual: (cst.GreaterThan, ">="),
    cst.Equal: (cst.NotEqual, "=="),
    cst.NotEqual: (cst.Equal, "!="),
    cst.Is: (cst.IsNot, "is"),
    cst.IsNot: (cst.Is, "is not"),
    cst.In: (cst.NotIn, "in"),
    cst.NotIn: (cst.In, "not in"),
}


def comparison_flip(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """`<` <-> `<=`, `>` <-> `>=`, `==` <-> `!=`, `is` <-> `is not`, `in` <-> `not in`."""
    for target in _nodes(scope, cst.ComparisonTarget):
        op = target.operator
        if type(op) not in _FLIPS:
            continue
        flipped, old_text = _FLIPS[type(op)]
        new_op = flipped(
            whitespace_before=op.whitespace_before, whitespace_after=op.whitespace_after
        )
        new = target.with_changes(operator=new_op)
        comparison = ctx.parents.get(target, target)
        description = f"`{old_text}` -> `{_FLIPS[flipped][1]}` in `{ctx.code(comparison)}`"
        yield Site("comparison_flip", target, new, description)


def off_by_one(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """±1 on integer constants; for `x - 1` / `x + 1`, also drop the 1 (`x`)."""
    for number in _nodes(scope, cst.Integer):
        try:
            value = int(number.value.replace("_", ""), 0)
        except ValueError:
            continue
        parent = ctx.parents.get(number)
        index_arithmetic = (
            isinstance(parent, cst.BinaryOperation)
            and parent.right is number
            and isinstance(parent.operator, cst.Add | cst.Subtract)
            and value == 1
        )
        if index_arithmetic:
            sign = "+" if isinstance(parent.operator, cst.Add) else "-"
            yield Site(
                "off_by_one", parent, parent.left, f"drop `{sign} 1` from `{ctx.code(parent)}`"
            )
        changes = [value + 1] if index_arithmetic else [value - 1, value + 1]
        for changed in changes:
            new: cst.BaseExpression = number.with_changes(value=str(abs(changed)))
            if changed < 0:  # a negative literal is unary minus on a positive one
                new = cst.UnaryOperation(operator=cst.Minus(), expression=new)
            in_comparison = isinstance(parent, cst.ComparisonTarget)
            context = ctx.parents.get(parent) if in_comparison else parent
            where = ctx.code(context) if context is not None else number.value
            yield Site("off_by_one", number, new, f"`{number.value}` -> `{changed}` in `{where}`")


def boolean_swap(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """`and` <-> `or`."""
    for node in _nodes(scope, cst.BooleanOperation):
        op = node.operator
        swapped_type = cst.Or if isinstance(op, cst.And) else cst.And
        swapped = swapped_type(
            whitespace_before=op.whitespace_before, whitespace_after=op.whitespace_after
        )
        new = node.with_changes(operator=swapped)
        old_name, new_name = ("and", "or") if isinstance(op, cst.And) else ("or", "and")
        yield Site("boolean_swap", node, new, f"`{old_name}` -> `{new_name}` in `{ctx.code(node)}`")


_EXITS = (cst.Raise, cst.Return, cst.Continue, cst.Break)


def removed_guard(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """Delete an `if` without `else` whose block ends by leaving (raise/return/continue/break)."""
    for node in _nodes(scope, cst.If):
        if node.orelse is not None:
            continue
        block = node.body
        last = block.body[-1] if block.body else None
        if isinstance(last, cst.SimpleStatementLine):
            last = last.body[-1]
        if not isinstance(last, _EXITS):
            continue
        description = f"remove guard `if {ctx.code(node.test)}:`"
        parent = ctx.parents.get(node)
        siblings = list(parent.body) if isinstance(parent, cst.IndentedBlock | cst.Module) else []
        index = next((i for i, s in enumerate(siblings) if s is node), None)
        if index is None:
            yield Site("removed_guard", node, None, description)
        elif len(siblings) == 1:
            new = cst.SimpleStatementLine([cst.Pass()], leading_lines=node.leading_lines)
            yield Site("removed_guard", node, new, description)
        else:
            # Comments above the guard belong to the code, not the bug: keep them by moving
            # them onto the next statement (or dropping them if the guard was the last one).
            rest = siblings[:index] + siblings[index + 1 :]
            if index < len(rest):
                following = rest[index]
                rest[index] = following.with_changes(
                    leading_lines=[*node.leading_lines, *following.leading_lines]
                )
            new_parent = parent.with_changes(body=rest)
            yield Site("removed_guard", parent, new_parent, description, anchor=node)


def _value_type(value: cst.BaseExpression, types: dict[str, str]) -> str | None:
    if isinstance(value, cst.Integer):
        return "int"
    if isinstance(value, cst.Float):
        return "float"
    if isinstance(value, cst.SimpleString | cst.ConcatenatedString | cst.FormattedString):
        return "str"
    if isinstance(value, cst.Name):
        return "bool" if value.value in ("True", "False") else types.get(value.value)
    return None


def swapped_arguments(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """Swap two adjacent call arguments of the same known type (annotation or literal)."""
    for call in _nodes(scope, cst.Call):
        args = list(call.args)
        for i in range(len(args) - 1):
            a, b = args[i], args[i + 1]
            if a.star or b.star or (a.keyword is None) != (b.keyword is None):
                continue
            kind = _value_type(a.value, ctx.types)
            if kind is None or kind != _value_type(b.value, ctx.types):
                continue
            if ctx.code(a.value) == ctx.code(b.value):
                continue
            swapped = args[:i] + [a.with_changes(value=b.value), b.with_changes(value=a.value)]
            new = call.with_changes(args=swapped + args[i + 2 :])
            description = (
                f"swap `{ctx.code(a.value)}` and `{ctx.code(b.value)}` "
                f"in `{ctx.code(call.func)}(...)`"
            )
            yield Site("swapped_arguments", call, new, description)


_BOOLEAN_EXPRESSIONS = (cst.Comparison, cst.BooleanOperation)


def wrong_return(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """Negate a boolean return value; return None instead of any other value."""
    for node in _nodes(scope, cst.Return):
        value = node.value
        if value is None or (isinstance(value, cst.Name) and value.value == "None"):
            continue
        if isinstance(value, cst.UnaryOperation) and isinstance(value.operator, cst.Not):
            wrong: cst.BaseExpression = value.expression
        elif isinstance(value, cst.Name) and value.value in ("True", "False"):
            wrong = cst.Name("False" if value.value == "True" else "True")
        elif isinstance(value, _BOOLEAN_EXPRESSIONS):
            parenthesized = (
                value
                if value.lpar
                else value.with_changes(lpar=[cst.LeftParen()], rpar=[cst.RightParen()])
            )
            wrong = cst.UnaryOperation(operator=cst.Not(), expression=parenthesized)
        else:
            wrong = cst.Name("None")
        new = node.with_changes(value=wrong)
        yield Site(
            "wrong_return", node, new, f"`return {ctx.code(value)}` -> `return {ctx.code(wrong)}`"
        )


OPERATORS: dict[str, Callable[[cst.CSTNode, Context], Iterator[Site]]] = {
    "comparison_flip": comparison_flip,
    "off_by_one": off_by_one,
    "boolean_swap": boolean_swap,
    "removed_guard": removed_guard,
    "swapped_arguments": swapped_arguments,
    "wrong_return": wrong_return,
}


# --- Applying operators to a module ---------------------------------------------------


def _scopes(module: cst.Module, qualname: str) -> list[tuple[str, cst.CSTNode, dict[str, str]]]:
    """(qualname, node whose code may change, parameter types) for a symbol.

    A function: its body. A class: each method's body. An assignment: the statement.
    """
    name, _, method = qualname.partition(".")
    for statement in module.body:
        if isinstance(statement, cst.FunctionDef) and statement.name.value == name and not method:
            return [(qualname, statement.body, _param_types(module, statement))]
        if isinstance(statement, cst.ClassDef) and statement.name.value == name:
            methods = [
                node
                for node in statement.body.body
                if isinstance(node, cst.FunctionDef) and (not method or node.name.value == method)
            ]
            return [
                (f"{name}.{node.name.value}", node.body, _param_types(module, node))
                for node in methods
            ]
        if isinstance(statement, cst.SimpleStatementLine) and not method:
            for small in statement.body:
                targets = (
                    [t.target for t in small.targets]
                    if isinstance(small, cst.Assign)
                    else [small.target]
                    if isinstance(small, cst.AnnAssign)
                    else []
                )
                if any(isinstance(t, cst.Name) and t.value == name for t in targets):
                    return [(qualname, statement, {})]
    raise ValueError(f"symbol {qualname!r} not found")


def _param_types(module: cst.Module, function: cst.FunctionDef) -> dict[str, str]:
    params = function.params
    every = [*params.posonly_params, *params.params, *params.kwonly_params]
    return {
        p.name.value: module.code_for_node(p.annotation.annotation)
        for p in every
        if p.annotation is not None
    }


def mutations(
    source: str,
    qualname: str,
    operators: list[str] | None = None,
    table: dict[str, Callable[[cst.CSTNode, Context], Iterator[Site]]] = OPERATORS,
) -> list[Mutation]:
    """Every mutation of `qualname` in `source`, in a fixed order (scope, operator, position).

    `table` is the operator set: the bug operators above, or master.py's perf regressions.

    Mutations that leave the code unchanged or duplicate an earlier one are dropped.
    """
    wrapper = MetadataWrapper(cst.parse_module(source))
    module = wrapper.module
    positions = wrapper.resolve(PositionProvider)
    parents = wrapper.resolve(ParentNodeProvider)
    seen = {source}
    result = []
    for scope_name, scope, types in _scopes(module, qualname):
        ctx = Context(module, parents, types)
        for operator in operators or list(table):
            for site in table[operator](scope, ctx):
                if site.new is None:
                    changed = module.deep_remove(site.old)
                else:
                    changed = module.deep_replace(site.old, site.new)
                code = changed.code
                if code in seen:
                    continue
                seen.add(code)
                line = positions[site.anchor or site.old].start.line
                result.append(Mutation(operator, scope_name, line, site.description, code))
    return result


# --- Candidates -----------------------------------------------------------------------


def _diff(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=2,
        )
    )


def _changed_line(diff: str) -> str:
    lines = diff.splitlines()[2:]  # skip the ---/+++ header
    added = [line[1:] for line in lines if line.startswith("+")]
    removed = [line[1:] for line in lines if line.startswith("-")]
    return added[0] if added else f"(removed) {removed[0].strip()}" if removed else ""


def inject_bug(seed_id: str, concept: str, rng_seed: int) -> list[Candidate]:
    """Every single-bug mutant of the concept's symbols, ordered by rng_seed.

    Each candidate's starter files are the seed's starter with exactly one file changed.
    The same (seed, concept, rng_seed) always gives the same list.
    """
    files, concepts = load_seed(seed_id)
    base = starter_base(files)
    candidates = []
    for symbol in concept_entry(concepts, concept)["symbols"]:
        path, _, qualname = symbol.partition("::")
        for mutation in mutations(base[path], qualname):
            diff = _diff(path, base[path], mutation.source)
            candidates.append(
                Candidate(
                    operator=mutation.operator,
                    file=path,
                    line=mutation.line,
                    description=mutation.description,
                    target_symbols=[f"{path}::{mutation.qualname}"],
                    starter_files=base | {path: mutation.source},
                    diff=diff,
                    changed_line=_changed_line(diff),
                )
            )
    random.Random(rng_seed).shuffle(candidates)
    return candidates


def prefilter(
    seed_id: str, concept: str, candidates: list[Candidate], max_runs: int = MAX_RUNS
) -> list[Checked]:
    """Run the seed's tests on candidates in order, at most `max_runs` sandbox runs.

    Kept: the app imports and tests run, at least one test fails and at most 40% do, and at
    least one of the concept's tests fails (the visible split needs one). Kept candidates
    with 1-5 failing tests come first.
    """
    files, concepts = load_seed(seed_id)
    runtime = concepts["runtime"]
    concept_tests = set(concept_entry(concepts, concept)["tests"])
    tests = {path: files[path] for path in test_modules(files)}
    checked = []
    for candidate in candidates[:max_runs]:
        result = run_tests(runtime, candidate.starter_files | tests, sorted(tests), timeout_s=60)
        if result.status != "ok":
            checked.append(Checked(candidate, False, f"tests could not run ({result.status})"))
            continue
        failing = failing_functions(result)
        failing_count = sum(t.outcome != "passed" for t in result.tests)
        total = len(result.tests)
        if failing_count == 0:
            reason, kept = "no test fails", False
        elif failing_count > MAX_FAILING_SHARE * total:
            reason, kept = f"too many tests fail (> {MAX_FAILING_SHARE:.0%})", False
        elif not failing & concept_tests:
            reason, kept = f"no {concept} test fails", False
        else:
            reason, kept = "kept", True
        checked.append(Checked(candidate, kept, reason, failing_count, total, frozenset(failing)))
    return checked


def ranked(checked: list[Checked]) -> list[Checked]:
    """Kept candidates, those with 1-5 failing tests first; otherwise in rng order."""
    kept = [c for c in checked if c.kept]
    return sorted(kept, key=lambda c: c.failing not in PREFERRED_FAILING)


# --- Draft task -----------------------------------------------------------------------


def draft_novice_task(seed_id: str, concept: str, chosen: Checked, rng_seed: int) -> BuiltTask:
    """A validated draft task_spec (tier novice, mode seed) for one pre-filtered candidate."""
    files, concepts = load_seed(seed_id)
    entry = concept_entry(concepts, concept)
    candidate = chosen.candidate
    visible, hidden = split_concept_tests(files, entry["tests"], set(chosen.failing_tests))
    spec = {
        "task_id": f"{seed_id}-{concept}-novice-{rng_seed}",
        "version": 1,
        "tier": "novice",
        "kind": "domain",
        "mode": "seed",
        "seed_id": seed_id,
        "runtime": concepts["runtime"],
        "dsa_tags": [],
        "statement_md": STATEMENT_PLACEHOLDER.format(concept=concept),
        "repo_tour_md": files.get("README_TOUR.md", ""),
        "starter_files": candidate.starter_files,
        "reference_ref": f"seeds/{seed_id}",
        "target_symbols": candidate.target_symbols,
        "entry_symbols": entry["symbols"],
        "visible_tests": visible,
        "hidden_tests": hidden,
        "dsa_cases": None,
        "perf": None,
        "time_budget_min": NOVICE_TIME_BUDGET_MIN,
        "random_seeds": [rng_seed],
        "certificate": draft_certificate([candidate.file]),
        "ai_solve_rate": 0.0,
        "difficulty_index": 0.0,
    }
    spec = grading.derive_test_ids(spec)
    reference = {candidate.file: files[candidate.file]}
    return validate_task(spec, reference, [candidate.file])


# --- CLI ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("seed")
    parser.add_argument("concept")
    parser.add_argument("--rng-seed", type=int, default=0)
    parser.add_argument("--max-runs", type=int, default=MAX_RUNS)
    parser.add_argument("--no-draft", action="store_true", help="skip building the draft spec")
    args = parser.parse_args(argv)

    candidates = inject_bug(args.seed, args.concept, args.rng_seed)
    print(
        f"inject_bug({args.seed}, {args.concept}, rng_seed={args.rng_seed}): "
        f"{len(candidates)} candidates"
    )
    for i, c in enumerate(candidates, 1):
        print(f"  {i:2}. {c.operator:<17} {c.target_symbols[0]}:{c.line}  {c.description}")

    print(
        f"\nPre-filter in the sandbox (at most {args.max_runs} runs): keep if the tests run, "
        f"1 to 40% fail and a {args.concept} test fails; prefer 1-5 failing"
    )
    checked = prefilter(args.seed, args.concept, candidates, args.max_runs)
    for i, c in enumerate(checked, 1):
        counts = f"{c.failing}/{c.total} failing" if c.total else "-"
        print(
            f"  {i:2}. {'KEPT' if c.kept else 'drop':<5} {counts:<15} {c.reason:<30} "
            f"{c.candidate.operator}: {c.candidate.description}"
        )
    best = ranked(checked)
    print(f"\n{len(best)} kept of {len(checked)} checked.")
    if not best:
        return
    for c in best:
        print(
            f"\n--- {c.candidate.operator} at {c.candidate.target_symbols[0]}:"
            f"{c.candidate.line} ({c.failing}/{c.total} failing)"
        )
        print(c.candidate.diff, end="")
    if args.no_draft:
        return
    built = draft_novice_task(args.seed, args.concept, best[0], args.rng_seed)
    spec, validation = built.spec, built.validation
    print(
        f"\nDraft task {spec['task_id']} (tier {spec['tier']}, mode {spec['mode']}) from the "
        f"first kept candidate:"
    )
    print(f"  target_symbols: {spec['target_symbols']}")
    print(f"  visible tests ({len(spec['visible_test_ids'])}): {spec['visible_test_ids']}")
    print(
        f"  hidden tests: {len(spec['hidden_test_ids'])} in "
        f"{sorted({i.split('::')[0] for i in spec['hidden_test_ids']})}"
    )
    print(f"  validation: starter {validation['starter']}, reference {validation['reference']}")
    print(f"  statement_md: {spec['statement_md']}")


if __name__ == "__main__":
    main()
