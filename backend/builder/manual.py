"""Demo tasks (P1.3): a Novice pagination bug and one DSA problem.

The pagination bug comes from the mutation engine (builder/mutate.py, P2.2): the engine's
off-by-one candidate at paginate()'s offset, `(page - 1)` -> `(page - 2)`, which `make e2e`
knows how to fix. It fails 3 tests, all pagination ones, so it passes the gate's Novice
rules (backend/gate). If the engine stops producing it, the hand-written AST transform
below is the fallback. Building
needs Docker: test ids are collected and both tasks are validated in the sandbox (the
starter fails at least one visible test; the reference passes everything).
"""

import ast
import json
from typing import Any

from app import grading
from builder import mutate
from builder.seeds import DSA_DIR, SEEDS_DIR, seed_files
from builder.tasks import (
    BuiltTask,
    choose_visible,
    collect_test_names,
    draft_certificate,
    split_test_module,
    validate_task,
)
from runner import run_tests

EXPENSES_SEED = "py-fastapi-expenses"
# The hand-built demo tasks below; LLM enrichment (enrich.py) leaves them untouched.
DEMO_TASK_IDS = frozenset({"expenses-pagination", "dsa-longest-unique-substring"})
PAGINATION_TESTS = "tests/test_pagination.py"
HIDDEN_PAGINATION_TESTS = "tests/test_pagination_hidden.py"
DSA_PROBLEM = "longest_unique_substring"
DSA_CASES_SEED = 20261031  # dsa/longest_unique_substring/make_cases.py
DEMO_RNG_SEED = 1031
# The demo bug as it appears in the starter; e2e/demo.mjs pastes the fix for this line.
DEMO_BUG_LINE = "offset = (page - 2) * page_size"

PAGINATION_STATEMENT = """\
## Expenses list pages are wrong

Users of the expenses API report that paging through `GET /expenses` skips data:
the first page doesn't start with their first expense, and the last page is often
empty even though `total` says there are more.

Find and fix the bug so that `page` and `page_size` return the right slice of the
filtered, sorted expenses. Keep the response shape (`items`, `page`, `page_size`,
`total`, `has_next`) unchanged. Run the visible tests to check your fix; more tests
run when you submit.
"""


# --- Bug injection --------------------------------------------------------------------


def inject_offset_bug(source: str) -> str:
    """In paginate(), turn `offset = (page - 1) * page_size` into `offset = (page - 2) * page_size`.

    Located with the AST and applied as a text splice, so the rest of the file keeps its
    formatting. Deterministic; raises if the pattern isn't there exactly once.
    """
    tree = ast.parse(source)
    paginate = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "paginate"), None
    )
    if paginate is None:
        raise ValueError("paginate() not found")
    sites = [
        node.value.left.right
        for node in ast.walk(paginate)
        if isinstance(node, ast.Assign)
        and [getattr(t, "id", None) for t in node.targets] == ["offset"]
        and isinstance(node.value, ast.BinOp)
        and isinstance(node.value.op, ast.Mult)
        and isinstance(node.value.left, ast.BinOp)
        and isinstance(node.value.left.op, ast.Sub)
        and isinstance(node.value.left.right, ast.Constant)
        and node.value.left.right.value == 1
    ]
    if len(sites) != 1:
        raise ValueError(f"expected one `offset = (page - 1) * ...`, found {len(sites)}")
    one = sites[0]
    lines = source.splitlines(keepends=True)
    line = lines[one.lineno - 1].encode()
    # UTF-8 byte offsets
    lines[one.lineno - 1] = (line[: one.col_offset] + b"2" + line[one.end_col_offset :]).decode()
    return "".join(lines)


def demo_starter_utils(reference_utils: str) -> str:
    """app/utils.py with the demo bug: the engine's candidate, else the hand transform."""
    for candidate in mutate.inject_bug(EXPENSES_SEED, "pagination", DEMO_RNG_SEED):
        if (
            candidate.operator == "off_by_one"
            and candidate.target_symbols == ["app/utils.py::paginate"]
            and candidate.changed_line.strip() == DEMO_BUG_LINE
        ):
            return candidate.starter_files["app/utils.py"]
    return inject_offset_bug(reference_utils)


# --- Domain task ----------------------------------------------------------------------


def build_pagination_task() -> BuiltTask:
    seed_dir = SEEDS_DIR / EXPENSES_SEED
    files = seed_files(seed_dir)
    reference_utils = files["app/utils.py"]
    starter = {
        path: content
        for path, content in files.items()
        if path.startswith("app/") or path in ("pytest.ini", "tests/conftest.py")
    }
    starter["app/utils.py"] = demo_starter_utils(reference_utils)

    pagination = files[PAGINATION_TESTS]
    names = collect_test_names(pagination)
    visible_names = choose_visible(names, _failing_functions(starter, pagination))
    visible_source, hidden_source = split_test_module(pagination, set(visible_names))
    other_tests = sorted(p for p in files if p.startswith("tests/test_") and p != PAGINATION_TESTS)

    spec = {
        "task_id": "expenses-pagination",
        "version": 1,
        "tier": "novice",
        "kind": "domain",
        "mode": "seed",
        "seed_id": EXPENSES_SEED,
        "runtime": "python311",
        "dsa_tags": [],
        "statement_md": PAGINATION_STATEMENT,
        "repo_tour_md": files["README_TOUR.md"],
        "starter_files": starter,
        "reference_ref": f"seeds/{EXPENSES_SEED}",
        "target_symbols": ["app/utils.py::paginate"],
        "entry_symbols": ["app/routes.py::list_expenses"],
        "visible_tests": [{"path": PAGINATION_TESTS, "content": visible_source}],
        "hidden_tests": [{"path": HIDDEN_PAGINATION_TESTS, "content": hidden_source}]
        + [{"path": p, "content": files[p]} for p in other_tests],
        "dsa_cases": None,
        "perf": None,
        "time_budget_min": 35,
        "random_seeds": [],
        "ai_solve_rate": 0.0,
        "difficulty_index": 0.0,
    }
    spec = grading.derive_test_ids(spec | {"certificate": draft_certificate(["app/utils.py"])})
    return validate_task(spec, {"app/utils.py": reference_utils}, ["app/utils.py"])


def _failing_functions(starter: dict[str, str], pagination: str) -> set[str]:
    """Names of the pagination tests that fail on the starter (parametrized ones collapsed)."""
    result = run_tests("python311", starter | {PAGINATION_TESTS: pagination}, [PAGINATION_TESTS])
    if result.status != "ok":
        raise ValueError(f"pagination tests could not run on the starter: {result.status}")
    return {t.id.split("::", 1)[1].split("[", 1)[0] for t in result.tests if t.outcome != "passed"}


# --- DSA task -------------------------------------------------------------------------


def dsa_task_spec() -> dict[str, Any]:
    """The DSA spec, test ids filled in. Needs no Docker; build_dsa_task validates it."""
    problem_dir = DSA_DIR / DSA_PROBLEM
    cases = json.loads((problem_dir / "cases.json").read_text())
    entry = "solution.py::length_of_longest_substring"
    spec = {
        "task_id": "dsa-longest-unique-substring",
        "version": 1,
        "tier": "novice",
        "kind": "dsa",
        "mode": "seed",
        "seed_id": DSA_PROBLEM,
        "runtime": "python311",
        "dsa_tags": ["sliding_window"],
        "statement_md": (problem_dir / "problem.md").read_text(),
        "repo_tour_md": "",
        "starter_files": {"solution.py": (problem_dir / "stub.py").read_text()},
        "reference_ref": f"dsa/{DSA_PROBLEM}/reference.py",
        "target_symbols": [entry],
        "entry_symbols": [entry],
        "visible_tests": [],
        "hidden_tests": [],
        "dsa_cases": {"visible": cases["visible"], "hidden": cases["hidden"], "comparator": None},
        "perf": None,
        "time_budget_min": 25,
        "random_seeds": [DSA_CASES_SEED],
        "certificate": draft_certificate(["solution.py"]),
        "ai_solve_rate": 0.0,
        "difficulty_index": 0.0,
    }
    return grading.derive_test_ids(spec)


def build_dsa_task() -> BuiltTask:
    reference = (DSA_DIR / DSA_PROBLEM / "reference.py").read_text()
    return validate_task(dsa_task_spec(), {"solution.py": reference}, ["solution.py"])
