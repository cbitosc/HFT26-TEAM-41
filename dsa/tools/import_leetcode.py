"""Import LeetCodeDataset problems into the DSA bank (P2.6). Run with `make dsa-import`.

1. Download the dataset at a pinned Hugging Face revision into dsa/raw/ (git-ignored),
   checking each file's sha256.
2. Filter with plain parsing only, never exec/eval: the signature (ast of the starter code)
   must use JSON types only; every tag must map to dsa/taxonomy.yaml; case inputs are
   parsed as keyword arguments with ast and literal_eval, outputs with literal_eval;
   anything that doesn't parse cleanly is dropped.
3. Pick problems per difficulty, spread across tags, and run each reference solution on
   every case in the sandbox. Expected values are the sandbox outputs; a problem whose
   outputs disagree with the dataset, or that errors or times out, is dropped.
4. Write dsa/<id>/ (problem.json, reference.py, stub.py, problem.md, cases.json). The
   original description goes to dsa/raw/descriptions/<id>.md only: it is LeetCode's text,
   used as rewrite input, never committed and never served.
5. Re-apply the practice-only split (builder.dsa_bank.mark_practice_only) to the whole bank.

Runs in the worker container (sandbox access) with the repo's dsa/ mounted at --out.
"""

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from app.dsa import _HARNESS, CASE_TIMEOUT_S, RUN_OVERHEAD_S, matches
from builder.dsa_bank import (
    BankProblem,
    identity_names,
    mark_practice_only,
    python_stub,
    statement_md,
)
from builder.dsa_rewrite import JS_RESERVED, PY_RESERVED, template_story
from contracts_gen.task_spec import Comparator
from profiler.taxonomy import TIERS, load_taxonomy
from runner import run_program

DATASET = "newfacade/LeetCodeDataset"
REVISION = "215604aeed660029df7de2fea5a4d7b6ed476a08"
FILES = {
    "LeetCodeDataset-train.jsonl": "ef7d64d34b092859607c1010bdd23540860a8cfff2ed7aeb0fe82e0ad524919b",
    "LeetCodeDataset-test.jsonl": "aec951945feb555b4c72783519452a7a0437ca8c6e5624a83d0ae888718fa4ed",
}
URL = "https://huggingface.co/datasets/{dataset}/resolve/{revision}/{name}"

# Problems kept per difficulty (80-120 in all). Easy -> novice, Medium -> adept and
# master, Hard -> master; a tier is dropped when one of the problem's topics isn't
# allowed for it in the taxonomy.
QUOTA = {"easy": 35, "medium": 40, "hard": 25}
DIFFICULTY_TIERS = {"easy": ["novice"], "medium": ["adept", "master"], "hard": ["master"]}
VISIBLE = 5
MIN_HIDDEN = 10
MAX_HIDDEN = 60
MAX_CASE_CHARS = 8000
SAFE_INT = 2**53 - 1  # JavaScript numbers are exact up to here
FLOAT_TOLERANCE = 1e-5
WORKERS = 4

# Same imports the dataset's prompt gives every solution.
HEADER = """\
import random
import functools
import collections
import string
import math
import datetime

from typing import *
from functools import *
from collections import *
from itertools import *
from heapq import *
from bisect import *
from string import *
from operator import *
from math import *

inf = float('inf')
"""


class Skip(Exception):
    pass


# --- Download -------------------------------------------------------------------------


def download(raw: Path) -> list[dict[str, Any]]:
    raw.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, sha256 in FILES.items():
        path = raw / name
        if not path.is_file() or _sha256(path) != sha256:
            url = URL.format(dataset=DATASET, revision=REVISION, name=name)
            print(f"downloading {url}", flush=True)
            with urllib.request.urlopen(url, timeout=120) as response, open(path, "wb") as f:
                shutil.copyfileobj(response, f)
        if _sha256(path) != sha256:
            raise SystemExit(f"{name}: sha256 mismatch; refusing to import")
        with open(path, encoding="utf-8") as f:
            rows += [json.loads(line) for line in f]
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- Parsing (no exec, no eval) -------------------------------------------------------


def annotation(node: ast.expr | None) -> str:
    """ast annotation -> JSON-type annotation string, or Skip."""
    if isinstance(node, ast.Name) and node.id in ("int", "float", "bool", "str"):
        return node.id
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        outer = node.value.id
        if outer in ("List", "list"):
            return f"list[{annotation(node.slice)}]"
        if outer in ("Dict", "dict") and isinstance(node.slice, ast.Tuple):
            key, value = node.slice.elts
            if annotation(key) == "str":
                return f"dict[str, {annotation(value)}]"
    raise Skip(f"non-JSON type {ast.unparse(node) if node else 'missing'}")


def signature(starter_code: str) -> tuple[str, list[tuple[str, str]], str]:
    """(method name, [(param, type)], return type) of the one Solution method."""
    tree = ast.parse(starter_code + "\n        pass\n")
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    if len(classes) != 1 or classes[0].name != "Solution":
        raise Skip("not a single Solution class")
    methods = [n for n in classes[0].body if isinstance(n, ast.FunctionDef)]
    if len(methods) != 1:
        raise Skip("not a single method")
    method = methods[0]
    args = method.args
    if args.vararg or args.kwarg or args.kwonlyargs or args.defaults or args.posonlyargs:
        raise Skip("unusual parameters")
    if not args.args or args.args[0].arg != "self":
        raise Skip("not an instance method")
    params = [(a.arg, annotation(a.annotation)) for a in args.args[1:]]
    if not params:
        raise Skip("no parameters")
    return method.name, params, annotation(method.returns)


def parse_input(text: str, names: list[str]) -> dict[str, Any]:
    """'nums = [1,2], k = 3' -> {"nums": [1, 2], "k": 3}, via ast keyword arguments only."""
    call = ast.parse(f"f({text})", mode="eval").body
    if not isinstance(call, ast.Call) or call.args:
        raise Skip("input is not keyword arguments")
    values = {}
    for kw in call.keywords:
        if kw.arg is None or kw.arg in values:
            raise Skip("bad keyword")
        values[kw.arg] = to_json(ast.literal_eval(kw.value))
    if sorted(values) != sorted(names):
        raise Skip("input names differ from the signature")
    return {name: values[name] for name in names}


def to_json(value: Any) -> Any:
    """literal_eval result -> plain JSON (tuples become lists), or Skip."""
    if value is None or isinstance(value, bool | str):
        return value
    if isinstance(value, int):
        if abs(value) > SAFE_INT:
            raise Skip("integer too large for JavaScript")
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise Skip("non-finite float")
        return value
    if isinstance(value, list | tuple):
        return [to_json(v) for v in value]
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return {k: to_json(v) for k, v in value.items()}
    raise Skip(f"non-JSON value {type(value).__name__}")


def conforms(value: Any, kind: str) -> bool:
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "float":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "str":
        return isinstance(value, str)
    if kind.startswith("list["):
        return isinstance(value, list) and all(conforms(v, kind[5:-1]) for v in value)
    if kind.startswith("dict[str, "):
        return isinstance(value, dict) and all(conforms(v, kind[10:-1]) for v in value.values())
    return False


def snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def candidate(row: dict[str, Any], taxonomy) -> dict[str, Any]:
    """The parsed problem (cases not yet checked in the sandbox), or Skip."""
    canonical = [taxonomy.canonical(t) for t in row["tags"]]
    if not canonical or None in canonical:
        raise Skip("a tag is not in the taxonomy")
    tags = sorted(set(canonical))
    difficulty = row["difficulty"].lower()
    tiers = [
        tier
        for tier in DIFFICULTY_TIERS[difficulty]
        if all(tier in taxonomy.topic_tiers[tag] for tag in tags)
    ]
    if not tiers:
        raise Skip("no tier allows all its topics")
    method, params, returns = signature(row["starter_code"])
    entry = snake(method)
    for name in [entry] + [p for p, _ in params]:
        if name in JS_RESERVED or name.startswith("_bank"):
            raise Skip(f"{name} is reserved in JS")
    if entry in PY_RESERVED or re.search(rf"\b{entry}\b", row["completion"]):
        raise Skip(f"{entry} would shadow a name the reference uses")

    names = [p for p, _ in params]
    types = dict(params)
    cases = []
    for item in row["input_output"]:
        try:
            given = parse_input(item["input"], names)
            expected = to_json(ast.literal_eval(item["output"]))
        except (Skip, SyntaxError, ValueError, TypeError, MemoryError, RecursionError):
            continue
        if not all(conforms(given[n], types[n]) for n in names) or not conforms(expected, returns):
            continue
        if len(json.dumps(given)) + len(json.dumps(expected)) > MAX_CASE_CHARS:
            continue
        if any(json.dumps(given, sort_keys=True) == json.dumps(c[0], sort_keys=True) for c in cases):
            continue
        cases.append((given, expected))
    if len(cases) < VISIBLE + MIN_HIDDEN:
        raise Skip(f"only {len(cases)} usable cases")

    description = row["problem_description"]
    comparator = None
    if "float" in returns:
        comparator = {"kind": "float_tolerance", "tolerance": FLOAT_TOLERANCE}
    elif returns.startswith("list[") and "any order" in description.lower():
        comparator = {"kind": "unordered_list", "tolerance": None}
    return {
        "id": row["task_id"].replace("-", "_"),
        "row": row,
        "difficulty": difficulty,
        "tiers": tiers,
        "tags": tags,
        "method": method,
        "entry": entry,
        "params": params,
        "returns": returns,
        "comparator": comparator,
        "cases": cases[: VISIBLE + MAX_HIDDEN],
    }


# --- Sandbox check --------------------------------------------------------------------


def reference_source(problem: dict[str, Any]) -> str:
    params = ", ".join(p for p, _ in problem["params"])
    return (
        f"{HEADER}\n\n{problem['row']['completion'].strip()}\n\n\n"
        f"def {problem['entry']}({params}):\n"
        f"    return Solution().{problem['method']}({params})\n"
    )


def check_in_sandbox(problem: dict[str, Any]) -> list[Any]:
    """The reference's outputs on every case (sandbox), or Skip."""
    harness_path, harness = _HARNESS["python311"]
    inputs = [{"id": str(i), "input": given} for i, (given, _) in enumerate(problem["cases"])]
    files = {
        "reference.py": reference_source(problem),
        harness_path: harness,
        "_harness/inputs.json": json.dumps(inputs),
    }

    def command(report_path: str) -> list[str]:
        args = ["_harness/inputs.json", report_path, "reference.py", problem["entry"]]
        return ["python", "-I", harness_path, *args, str(CASE_TIMEOUT_S)]

    timeout_s = RUN_OVERHEAD_S + int(len(inputs) * CASE_TIMEOUT_S)
    run = run_program("python311", files, command, timeout_s=timeout_s)
    entries = (run.report or {}).get("cases")
    if run.status != "ok" or not isinstance(entries, list) or len(entries) != len(inputs):
        raise Skip(f"sandbox run {run.status}: {(run.report or {}).get('fatal', '')}"[:200])
    comparator = Comparator(**problem["comparator"]) if problem["comparator"] else None
    outputs = []
    for entry, (_, expected) in zip(entries, problem["cases"], strict=True):
        if "error" in entry:
            raise Skip(f"reference error: {entry['error'][:120]}")
        if not matches(entry["output"], expected, comparator):
            raise Skip("reference output disagrees with the dataset")
        outputs.append(entry["output"])
    return outputs


# --- Selection and writing ------------------------------------------------------------


def spread(problems: list[dict[str, Any]], tag_counts: Counter) -> list[dict[str, Any]]:
    """Round-robin over each problem's rarest tag, so the bank covers many topics."""
    groups: dict[str, list] = defaultdict(list)
    for p in sorted(problems, key=lambda p: p["row"]["question_id"]):
        groups[min(p["tags"], key=lambda t: (tag_counts[t], t))].append(p)
    order = []
    while any(groups.values()):
        for tag in sorted(groups):
            if groups[tag]:
                order.append(groups[tag].pop(0))
    return order


def write_problem(out: Path, problem: dict[str, Any], outputs: list[Any]) -> BankProblem:
    folder = out / problem["id"]
    folder.mkdir()
    row = problem["row"]
    cases = [
        {"input": given, "expected": output}
        for (given, _), output in zip(problem["cases"], outputs, strict=True)
    ]
    # The smallest cases are shown; the rest (in dataset order) form the hidden pool.
    by_size = sorted(range(len(cases)), key=lambda i: (len(json.dumps(cases[i])), i))
    visible_idx = sorted(by_size[:VISIBLE])
    hidden = [c for i, c in enumerate(cases) if i not in visible_idx][:MAX_HIDDEN]
    cases_json = {
        "visible": [{"id": f"v{n}"} | cases[i] for n, i in enumerate(visible_idx, start=1)],
        "hidden": [{"id": f"h{n:02d}"} | c for n, c in enumerate(hidden, start=1)],
    }
    meta = {
        "id": problem["id"],
        "difficulty": problem["difficulty"],
        "tiers": problem["tiers"],
        "tags": problem["tags"],
        "entry_point": problem["entry"],
        "signature": {
            "params": [{"name": n, "type": t} for n, t in problem["params"]],
            "returns": problem["returns"],
        },
        "comparator": problem["comparator"],
        "own_statement": False,
        "source": {
            "dataset": DATASET,
            "revision": REVISION,
            "task_id": row["task_id"],
            "question_id": row["question_id"],
        },
    }
    bank = BankProblem.model_validate(meta)
    names = identity_names(bank)
    (folder / "problem.json").write_text(json.dumps(meta, indent=1) + "\n")
    (folder / "cases.json").write_text(json.dumps(cases_json, indent=1) + "\n")
    (folder / "reference.py").write_text(reference_source(problem))
    (folder / "stub.py").write_text(python_stub(bank, names))
    statement = statement_md(
        bank, template_story(bank), names, "python311", cases_json["visible"]
    )
    (folder / "problem.md").write_text(statement)
    descriptions = out / "raw" / "descriptions"
    descriptions.mkdir(parents=True, exist_ok=True)
    (descriptions / f"{problem['id']}.md").write_text(row["problem_description"])
    return bank


def previous_imports(out: Path) -> tuple[list[Path], set[str]]:
    """Folders written by an earlier import, and dataset task ids already in the bank by hand."""
    imported, taken = [], set()
    for path in out.glob("*/problem.json"):
        source = json.loads(path.read_text()).get("source", {})
        if source.get("dataset") == DATASET and source.get("revision"):
            imported.append(path.parent)
        elif source.get("task_id"):
            taken.add(source["task_id"])
    return imported, taken


def chown_like(out: Path) -> None:
    """Files written as root in the container get the owner of the dsa/ directory."""
    owner = out.stat()
    if os.geteuid() != 0:
        return
    for path in [out, *out.rglob("*")]:
        os.chown(path, owner.st_uid, owner.st_gid)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="the repo's dsa/ directory")
    args = parser.parse_args()
    out: Path = args.out
    rows = download(out / "raw")
    taxonomy = load_taxonomy(out / "taxonomy.yaml")
    imported, taken = previous_imports(out)
    for folder in imported:
        shutil.rmtree(folder)

    skipped: Counter = Counter()
    candidates = []
    for row in rows:
        if row["task_id"] in taken:
            continue
        try:
            candidates.append(candidate(row, taxonomy))
        except (Skip, SyntaxError, ValueError) as exc:
            skipped[str(exc).split(":")[0][:50]] += 1
    tag_counts = Counter(tag for c in candidates for tag in c["tags"])
    print(f"{len(rows)} rows, {len(candidates)} pass the filters", flush=True)

    kept: list[BankProblem] = []
    with ThreadPoolExecutor(WORKERS) as pool:
        for difficulty, quota in QUOTA.items():
            order = spread([c for c in candidates if c["difficulty"] == difficulty], tag_counts)
            accepted = 0
            for start in range(0, len(order), WORKERS):
                if accepted >= quota:
                    break
                batch = order[start : start + WORKERS]
                futures = [pool.submit(check_in_sandbox, p) for p in batch]
                for problem, future in zip(batch, futures, strict=True):
                    try:
                        outputs = future.result()
                    except Skip as exc:
                        skipped[f"sandbox: {str(exc)[:40]}"] += 1
                        continue
                    if accepted < quota:
                        kept.append(write_problem(out, problem, outputs))
                        accepted += 1
            print(f"{difficulty}: {accepted} problems", flush=True)
    practice = mark_practice_only(out)
    print(f"practice-only: {len(practice)} problems", flush=True)
    chown_like(out)

    print(f"\nkept {len(kept)} problems; skipped: {dict(skipped.most_common(12))}")
    tiers = Counter(t for p in kept for t in p.tiers)
    tags = Counter(t for p in kept for t in p.tags)
    print("per tier:", {t: tiers[t] for t in TIERS})
    print("per tag:", dict(sorted(tags.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
