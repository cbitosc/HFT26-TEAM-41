"""Master tasks (P2.4): one P2.2 bug plus one performance regression, in different files.

Perf regressions are LibCST operators applied to the seed's perf-sensitive symbols
(concepts.yaml `perf_symbols`): a set/dict lookup becomes a list scan, a cache is bypassed,
a batched query becomes one query per item (N+1), an order-keeping de-duplication becomes
quadratic. A regression must keep every functional test passing.

Calibration in the runner: the reference's perf test runs CALIBRATION_RUNS times and
budget_ms = 3 × the median. A regressed starter that doesn't exceed the budget is rejected
and the next site is tried. No LLM calls.

    python -m builder.master SEED [CONCEPT ...] [--rng-seed N]
"""

import argparse
import math
import random
import statistics
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import libcst as cst

from app import grading
from builder.mutate import (
    Context,
    Site,
    _diff,
    _nodes,
    inject_bug,
    mutations,
    prefilter,
    ranked,
)
from builder.perf import PERF_DIR, run_with_perf
from builder.tasks import (
    STATEMENT_PLACEHOLDER,
    BuiltTask,
    concept_entry,
    draft_certificate,
    load_seed,
    split_concept_tests,
    starter_base,
    test_modules,
    validate_task,
)

CALIBRATION_RUNS = 5
BUDGET_FACTOR = 3
MAX_PERF_SITES = 6
MAX_BUG_RUNS = 6
PERF_TIMEOUT_S = 120
MASTER_TIME_BUDGET_MIN = 45


class MasterError(ValueError):
    """No Master task can be built; the message says why."""


# --- Perf operators -------------------------------------------------------------------
# Same shape as mutate.py's bug operators: (scope, context) -> Sites.


def _names(scope: cst.CSTNode) -> set[str]:
    return {node.value for node in _nodes(scope, cst.Name)}


def _fresh(scope: cst.CSTNode, *options: str) -> str:
    used = _names(scope)
    for name in options:
        if name not in used:
            return name
    name = options[0]
    while name in used:
        name += "_"
    return name


def _source(ctx: Context, node: cst.CSTNode) -> str:
    """Source of `node` with its original line breaks (ctx.code collapses them)."""
    text = ctx.module.code_for_node(node)
    if isinstance(node, cst.GeneratorExp) and not node.lpar:
        text = f"({text})"
    return text


def _assigned(scope: cst.CSTNode) -> Iterator[tuple[str, cst.Assign]]:
    for node in _nodes(scope, cst.Assign):
        if len(node.targets) == 1 and isinstance(node.targets[0].target, cst.Name):
            yield node.targets[0].target.value, node


def _is_call_to(node: cst.CSTNode, *names: str) -> bool:
    return (
        isinstance(node, cst.Call) and isinstance(node.func, cst.Name) and node.func.value in names
    )


def list_scan(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """A set used for `in` checks becomes a list; `d.get(k)` on a dict becomes a linear scan."""
    membership = {
        target.comparator.value
        for target in _nodes(scope, cst.ComparisonTarget)
        if isinstance(target.operator, cst.In | cst.NotIn)
        and isinstance(target.comparator, cst.Name)
    }
    dicts = set()
    for name, assign in _assigned(scope):
        value = assign.value
        if isinstance(value, cst.Dict | cst.DictComp) or _is_call_to(value, "dict"):
            dicts.add(name)
        if name not in membership:
            continue
        if _is_call_to(value, "set", "frozenset") and len(value.args) == 1:
            new: cst.BaseExpression = value.with_changes(func=cst.Name("list"))
        elif isinstance(value, cst.SetComp):
            new = cst.ListComp(elt=value.elt, for_in=value.for_in)
        elif isinstance(value, cst.Set):
            new = cst.List(elements=value.elements)
        else:
            continue
        yield Site("list_scan", value, new, f"`{name}` becomes a list: each `in {name}` scans it")

    for call in _nodes(scope, cst.Call):
        func = call.func
        if not (
            isinstance(func, cst.Attribute)
            and func.attr.value == "get"
            and isinstance(func.value, cst.Name)
            and func.value.value in dicts
            and 1 <= len(call.args) <= 2
            and not any(arg.keyword or arg.star for arg in call.args)
        ):
            continue
        name = func.value.value
        key, value = _fresh(scope, "key", "k"), _fresh(scope, "value", "v")
        default = ctx.code(call.args[1].value) if len(call.args) == 2 else "None"
        new = cst.parse_expression(
            f"next(({value} for {key}, {value} in {name}.items() "
            f"if {key} == {ctx.code(call.args[0].value)}), {default})"
        )
        yield Site("list_scan", call, new, f"`{ctx.code(call)}` scans `{name}.items()`")


_CACHE_DECORATORS = {"cache", "lru_cache"}


def _decorator_name(decorator: cst.Decorator) -> str | None:
    node = decorator.decorator
    if isinstance(node, cst.Call):
        node = node.func
    if isinstance(node, cst.Attribute):
        return node.attr.value
    return node.value if isinstance(node, cst.Name) else None


def cache_bypass(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """Drop `@cache`/`@lru_cache`, or ignore a cache lookup's result and always recompute.

    The lookup itself stays (`x = cache.get(k)`), so hit/miss counters still move; the
    `if x is None:` guard around the computation goes.
    """
    function = ctx.parents.get(scope)
    if isinstance(function, cst.FunctionDef):
        for decorator in function.decorators:
            if _decorator_name(decorator) in _CACHE_DECORATORS:
                kept = [d for d in function.decorators if d is not decorator]
                new = function.with_changes(decorators=kept)
                yield Site(
                    "cache_bypass", function, new, f"remove `@{ctx.code(decorator.decorator)}`"
                )

    for block in _nodes(scope, cst.IndentedBlock):
        body = list(block.body)
        for i in range(len(body) - 1):
            lookup, guard = body[i], body[i + 1]
            if not (
                isinstance(lookup, cst.SimpleStatementLine)
                and len(lookup.body) == 1
                and isinstance(assign := lookup.body[0], cst.Assign)
                and len(assign.targets) == 1
                and isinstance(target := assign.targets[0].target, cst.Name)
                and isinstance(call := assign.value, cst.Call)
                and isinstance(call.func, cst.Attribute)
                and call.func.attr.value == "get"
                and "cache" in ctx.code(call.func.value).lower()
            ):
                continue
            is_none_check = (
                isinstance(guard, cst.If)
                and guard.orelse is None
                and isinstance(guard.test, cst.Comparison)
                and isinstance(guard.test.left, cst.Name)
                and guard.test.left.value == target.value
                and len(guard.test.comparisons) == 1
                and isinstance(guard.test.comparisons[0].operator, cst.Is)
                and ctx.code(guard.test.comparisons[0].comparator) == "None"
            )
            if not is_none_check:
                continue
            inner = list(guard.body.body)
            inner[0] = inner[0].with_changes(leading_lines=guard.leading_lines)
            new_block = block.with_changes(body=body[: i + 1] + inner + body[i + 2 :])
            yield Site(
                "cache_bypass",
                block,
                new_block,
                f"ignore `{ctx.code(call)}`: always recompute `{target.value}`",
                anchor=guard,
            )


_QUERY_METHODS = {"execute", "scalars"}
_SINGLE_ROW = {"one", "one_or_none", "first", "scalar", "scalar_one", "scalar_one_or_none"}


def n_plus_one(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """`session.execute(stmt.where(col.in_(keys)))` becomes one query per key."""
    for query in _nodes(scope, cst.Call):
        if not (
            isinstance(query.func, cst.Attribute)
            and query.func.attr.value in _QUERY_METHODS
            and query.args
        ):
            continue
        in_calls = [
            call
            for call in _nodes(query.args[0].value, cst.Call)
            if isinstance(call.func, cst.Attribute)
            and call.func.attr.value == "in_"
            and len(call.args) == 1
        ]
        if len(in_calls) != 1:
            continue
        in_call = in_calls[0]
        # Follow a result chain such as `.tuples()` or `.all()`; skip single-row results.
        outer: cst.BaseExpression = query
        while (
            isinstance(attr := ctx.parents.get(outer), cst.Attribute)
            and isinstance(chained := ctx.parents.get(attr), cst.Call)
            and chained.func is attr
        ):
            if attr.attr.value in _SINGLE_ROW:
                break
            outer = chained
        else:
            keys = in_call.args[0].value
            base = keys.value if isinstance(keys, cst.Name) else ""
            singular = base[:-1] if base.endswith("s") and len(base) > 1 else ""
            var = _fresh(scope, *(n for n in (singular, "key") if n))
            row = _fresh(scope, "match", "found")
            equals = cst.Comparison(
                left=in_call.func.value,
                comparisons=[cst.ComparisonTarget(cst.Equal(), cst.Name(var))],
            )
            per_item = outer.deep_replace(in_call, equals)
            new = cst.parse_expression(
                f"[{row} for {var} in {_source(ctx, keys)} "
                f"for {row} in {cst.Module([]).code_for_node(per_item)}]"
            )
            yield Site(
                "n_plus_one",
                outer,
                new,
                f"`{ctx.code(in_call)}` becomes one query per item of `{ctx.code(keys)}`",
            )


def quadratic_dedup(scope: cst.CSTNode, ctx: Context) -> Iterator[Site]:
    """`xs = list(dict.fromkeys(items))` becomes a loop that checks `x not in xs` each time."""
    for block in _nodes(scope, cst.IndentedBlock):
        body = list(block.body)
        for i, statement in enumerate(body):
            if not (
                isinstance(statement, cst.SimpleStatementLine)
                and len(statement.body) == 1
                and isinstance(assign := statement.body[0], cst.Assign)
                and len(assign.targets) == 1
                and isinstance(target := assign.targets[0].target, cst.Name)
                and _is_call_to(assign.value, "list")
                and len(assign.value.args) == 1
                and isinstance(inner := assign.value.args[0].value, cst.Call)
                and ctx.code(inner.func) == "dict.fromkeys"
                and len(inner.args) == 1
            ):
                continue
            name = target.value
            value = _fresh(scope, "value", "item")
            items = _source(ctx, inner.args[0].value)
            loop = cst.parse_statement(
                f"for {value} in {items}:\n"
                f"    if {value} not in {name}:\n"
                f"        {name}.append({value})\n"
            )
            empty = statement.with_changes(body=[assign.with_changes(value=cst.List(elements=[]))])
            new_block = block.with_changes(body=body[:i] + [empty, loop] + body[i + 1 :])
            yield Site(
                "quadratic_dedup",
                block,
                new_block,
                f"`{name}` is de-duplicated with a linear `not in {name}` per item",
                anchor=statement,
            )


PERF_OPERATORS: dict[str, Callable[[cst.CSTNode, Context], Iterator[Site]]] = {
    "list_scan": list_scan,
    "cache_bypass": cache_bypass,
    "n_plus_one": n_plus_one,
    "quadratic_dedup": quadratic_dedup,
}


# --- Perf candidates and calibration --------------------------------------------------


@dataclass(frozen=True)
class PerfCandidate:
    operator: str
    file: str
    line: int
    description: str
    symbol: str
    perf_test: str
    input_gen: str
    source: str
    diff: str


@dataclass(frozen=True)
class SiteCheck:
    functional_failing: list[str]
    perf_ms: float | None


@dataclass(frozen=True)
class Tried:
    candidate: PerfCandidate
    kept: bool
    reason: str
    perf_ms: float | None
    budget_ms: int


@dataclass
class Calibration:
    chosen: PerfCandidate | None = None
    ref_runs: list[float] = field(default_factory=list)
    ref_ms: float = 0.0
    budget_ms: int = 0
    naive_ms: float = 0.0
    tried: list[Tried] = field(default_factory=list)


def perf_symbols(concepts: dict[str, Any]) -> list[dict[str, Any]]:
    return [entry for entry in concepts.get("perf_symbols", []) if entry.get("perf")]


def perf_candidates(seed_id: str, rng_seed: int) -> list[PerfCandidate]:
    """Every perf regression of the seed's perf symbols, ordered by rng_seed."""
    files, concepts = load_seed(seed_id)
    base = starter_base(files)
    candidates = []
    for entry in perf_symbols(concepts):
        path, _, qualname = entry["symbol"].partition("::")
        for mutation in mutations(base[path], qualname, table=PERF_OPERATORS):
            candidates.append(
                PerfCandidate(
                    operator=mutation.operator,
                    file=path,
                    line=mutation.line,
                    description=mutation.description,
                    symbol=entry["symbol"],
                    perf_test=entry["test"],
                    input_gen=entry["input_gen"],
                    source=mutation.source,
                    diff=_diff(path, base[path], mutation.source),
                )
            )
    random.Random(rng_seed).shuffle(candidates)
    return candidates


def budget_for(ref_runs: list[float]) -> int:
    return math.ceil(BUDGET_FACTOR * statistics.median(ref_runs))


def calibrate(
    candidates: list[PerfCandidate],
    reference_runs: Callable[[str], list[float]],
    check: Callable[[PerfCandidate], SiteCheck],
    max_sites: int = MAX_PERF_SITES,
) -> Calibration:
    """Try regressions in order until one keeps the functional tests green and exceeds the
    budget (3 × the reference's median on its perf test). `reference_runs(test)` measures
    the reference; `check(candidate)` runs the regressed starter."""
    result = Calibration()
    budgets: dict[str, tuple[list[float], int]] = {}
    for candidate in candidates[:max_sites]:
        if candidate.perf_test not in budgets:
            runs = reference_runs(candidate.perf_test)
            budgets[candidate.perf_test] = (runs, budget_for(runs))
        runs, budget = budgets[candidate.perf_test]
        checked = check(candidate)
        if checked.functional_failing:
            reason = f"breaks {len(checked.functional_failing)} functional tests"
        elif checked.perf_ms is None:
            reason = "perf test recorded no time"
        elif checked.perf_ms <= budget:
            reason = f"within budget ({checked.perf_ms:.1f} <= {budget} ms)"
        else:
            reason = "kept"
        kept = reason == "kept"
        result.tried.append(Tried(candidate, kept, reason, checked.perf_ms, budget))
        if kept:
            result.chosen = candidate
            result.ref_runs = runs
            result.ref_ms = statistics.median(runs)
            result.budget_ms = budget
            result.naive_ms = checked.perf_ms
            break
    return result


def _perf_files(files: dict[str, str], perf_test: str) -> dict[str, str]:
    """The chosen perf test module plus the perf directory's helpers (not other perf tests)."""
    test_path = perf_test.split("::", 1)[0]
    return {
        path: content
        for path, content in files.items()
        if path.startswith(PERF_DIR)
        and (path == test_path or not path.rsplit("/", 1)[-1].startswith("test_"))
    }


def sandbox_reference_runs(seed_id: str) -> Callable[[str], list[float]]:
    files, concepts = load_seed(seed_id)

    def runs(perf_test: str) -> list[float]:
        workspace = starter_base(files) | _perf_files(files, perf_test)
        measured = []
        for _ in range(CALIBRATION_RUNS):
            run = run_with_perf(
                concepts["runtime"], workspace, [perf_test.split("::")[0]], PERF_TIMEOUT_S
            )
            if (
                run.status != "ok"
                or run.perf_ms is None
                or any(t.outcome != "passed" for t in run.tests)
            ):
                raise MasterError(f"the reference fails its perf test {perf_test}: {run.status}")
            measured.append(run.perf_ms)
        return measured

    return runs


def sandbox_check(seed_id: str) -> Callable[[PerfCandidate], SiteCheck]:
    """One run per site: every functional test plus the site's perf test."""
    files, concepts = load_seed(seed_id)
    functional = {path: files[path] for path in test_modules(files)}

    def check(candidate: PerfCandidate) -> SiteCheck:
        workspace = (
            starter_base(files)
            | {candidate.file: candidate.source}
            | functional
            | _perf_files(files, candidate.perf_test)
        )
        paths = sorted(functional) + [candidate.perf_test.split("::")[0]]
        run = run_with_perf(concepts["runtime"], workspace, paths, PERF_TIMEOUT_S)
        if run.status == "timeout":
            return SiteCheck([], run.perf_ms)
        if run.status != "ok":
            return SiteCheck([f"(tests could not run: {run.status})"], None)
        failing = [t.id for t in run.tests if t.outcome != "passed"]
        return SiteCheck(failing, run.perf_ms)

    return check


# --- Draft task -----------------------------------------------------------------------


@dataclass(frozen=True)
class MasterTask:
    built: BuiltTask
    calibration: Calibration
    bug_concept: str
    bug_diff: str
    bug_description: str


def perf_budget_sentence(spec: dict[str, Any]) -> str:
    """The statement's perf requirement, written by code (P2.5 appends it to the LLM's text)."""
    function = spec["target_symbols"][-1].split("::", 1)[1]  # the perf symbol comes last
    return (
        f"Performance: a hidden test times `{function}` on a large dataset. It must finish "
        f"within {spec['perf']['budget_ms']} ms; slower code loses up to half of this task's "
        "score."
    )


def build_master(
    seed_id: str,
    concepts: list[str],
    rng_seed: int,
    reference_runs: Callable[[str], list[float]] | None = None,
    check: Callable[[PerfCandidate], SiteCheck] | None = None,
) -> MasterTask:
    """A validated draft Master task_spec: a bug from `concepts` + a calibrated perf regression."""
    files, seed = load_seed(seed_id)
    calibration = calibrate(
        perf_candidates(seed_id, rng_seed),
        reference_runs or sandbox_reference_runs(seed_id),
        check or sandbox_check(seed_id),
    )
    perf = calibration.chosen
    if perf is None:
        reasons = "; ".join(f"{t.candidate.operator}: {t.reason}" for t in calibration.tried)
        raise MasterError(f"no perf regression exceeds its budget ({reasons or 'no sites'})")

    for concept in concepts or list(seed["concepts"]):
        candidates = [c for c in inject_bug(seed_id, concept, rng_seed) if c.file != perf.file]
        best = ranked(prefilter(seed_id, concept, candidates, MAX_BUG_RUNS))
        if best:
            break
    else:
        raise MasterError(f"no bug outside {perf.file} in concepts {concepts}")
    bug = best[0].candidate
    entry = concept_entry(seed, concept)

    visible, hidden = split_concept_tests(files, entry["tests"], set(best[0].failing_tests))
    hidden += [{"path": p, "content": c} for p, c in _perf_files(files, perf.perf_test).items()]
    target_symbols = bug.target_symbols + [perf.symbol]
    spec = {
        "task_id": f"{seed_id}-{concept}-master-{rng_seed}",
        "version": 1,
        "tier": "master",
        "kind": "domain",
        "mode": "seed",
        "seed_id": seed_id,
        "runtime": seed["runtime"],
        "dsa_tags": [],
        "statement_md": "",
        "repo_tour_md": files.get("README_TOUR.md", ""),
        "starter_files": bug.starter_files | {perf.file: perf.source},
        "reference_ref": f"seeds/{seed_id}",
        "target_symbols": target_symbols,
        "entry_symbols": list(dict.fromkeys(entry["symbols"] + [perf.symbol])),
        "visible_tests": visible,
        "hidden_tests": sorted(hidden, key=lambda test: test["path"]),
        "dsa_cases": None,
        "perf": {"budget_ms": calibration.budget_ms, "input_gen": perf.input_gen},
        "time_budget_min": MASTER_TIME_BUDGET_MIN,
        "random_seeds": [rng_seed],
        "certificate": draft_certificate(sorted({bug.file, perf.file})),
        "ai_solve_rate": 0.0,
        "difficulty_index": 0.0,
    }
    spec["statement_md"] = (
        STATEMENT_PLACEHOLDER.format(concept=concept) + "\n\n" + perf_budget_sentence(spec)
    )
    spec = grading.derive_test_ids(spec)
    scope = sorted({bug.file, perf.file})
    built = validate_task(spec, {path: files[path] for path in scope}, scope)
    certificate = built.spec["certificate"] | {
        "perf_ref_ms": round(calibration.ref_ms, 3),
        "perf_naive_ms": round(calibration.naive_ms, 3),
    }
    built = BuiltTask(spec=built.spec | {"certificate": certificate}, validation=built.validation)
    return MasterTask(built, calibration, concept, bug.diff, bug.description)


# --- CLI ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("seed")
    parser.add_argument("concepts", nargs="*", help="bug concepts to try, in order (default: all)")
    parser.add_argument("--rng-seed", type=int, default=0)
    args = parser.parse_args(argv)

    candidates = perf_candidates(args.seed, args.rng_seed)
    print(f"Perf regressions in {args.seed} (rng_seed={args.rng_seed}): {len(candidates)}")
    for i, c in enumerate(candidates, 1):
        print(f"  {i:2}. {c.operator:<16} {c.symbol}:{c.line}  {c.description}")

    try:
        task = build_master(args.seed, args.concepts, args.rng_seed)
    except MasterError as exc:
        print(f"\nCannot build a Master task: {exc}")
        return 2
    cal, spec, validation = task.calibration, task.built.spec, task.built.validation
    print(
        f"\nCalibration ({CALIBRATION_RUNS} reference runs of {cal.chosen.perf_test}): "
        f"{', '.join(f'{ms:.1f}' for ms in cal.ref_runs)} ms; median {cal.ref_ms:.1f} ms; "
        f"budget = {BUDGET_FACTOR} x median = {cal.budget_ms} ms"
    )
    for t in cal.tried:
        measured = "-" if t.perf_ms is None else f"{t.perf_ms:.1f} ms"
        print(
            f"  {'KEPT' if t.kept else 'drop':<5} {t.candidate.operator:<16} {measured:>11}  "
            f"budget {t.budget_ms} ms  {t.reason}"
        )
    print(f"\n--- perf regression ({cal.chosen.operator}): {cal.chosen.description}")
    print(cal.chosen.diff, end="")
    print(f"\n--- bug ({task.bug_concept}): {task.bug_description}")
    print(task.bug_diff, end="")
    print(f"\nDraft task {spec['task_id']} (tier {spec['tier']}, mode {spec['mode']}):")
    print(f"  target_symbols: {spec['target_symbols']}")
    print(f"  scope_files: {spec['certificate']['scope_files']}")
    print(f"  perf: {spec['perf']}")
    print(
        f"  certificate: perf_ref_ms {spec['certificate']['perf_ref_ms']}, "
        f"perf_naive_ms {spec['certificate']['perf_naive_ms']}"
    )
    print(f"  visible tests ({len(spec['visible_test_ids'])}): {spec['visible_test_ids']}")
    hidden_files = sorted({i.split("::")[0] for i in spec["hidden_test_ids"]})
    print(f"  hidden tests: {len(spec['hidden_test_ids'])} in {hidden_files}")
    print(f"  validation: starter {validation['starter']}, reference {validation['reference']}")
    print(f"  statement_md: {spec['statement_md']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
