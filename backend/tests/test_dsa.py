"""DSA grading without Docker: comparison, results from a harness report, and the harness
script itself (run as a plain subprocess here; in the sandbox in test_dsa_docker.py)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app import dsa
from contracts_gen.task_spec import Comparator, DsaCase
from runner import ProgramRun

HARNESS = Path(dsa.__file__).resolve().parents[1] / "runner" / "harness" / "python_cases.py"
CASES = [
    DsaCase(id="a", input={"x": 1}, expected=2),
    DsaCase(id="b", input={"x": 2}, expected=4),
    DsaCase(id="c", input={"x": 3}, expected=6),
]
IDS = ["a", "b", "c"]


def program(report: dict | None, status: str = "ok") -> ProgramRun:
    return ProgramRun(
        status=status, exit_code=0, report=report, duration_ms=50, stdout_tail="", stderr_tail=""
    )


def outputs(*values) -> dict:
    return {
        "cases": [
            {"id": i, "output": v, "duration_ms": 1} for i, v in zip(IDS, values, strict=False)
        ]
    }


# --- Comparators ---


@pytest.mark.parametrize(
    ("output", "expected", "comparator", "same"),
    [
        (3, 3, None, True),
        (3, 3.0, None, False),  # exact JSON identity
        (True, 1, None, False),
        ({"a": [1, 2]}, {"a": [1, 2]}, None, True),
        ([1, 2, 3], [3, 1, 2], None, False),
        ([1, 2, 3], [3, 1, 2], Comparator(kind="unordered_list", tolerance=None), True),
        ([1, 1, 2], [1, 2, 2], Comparator(kind="unordered_list", tolerance=None), False),
        ([[1, 2], [3]], [[3], [1, 2]], Comparator(kind="unordered_list", tolerance=None), True),
        (0.1 + 0.2, 0.3, None, False),
        (0.1 + 0.2, 0.3, Comparator(kind="float_tolerance", tolerance=1e-9), True),
        ([1.0, 2.0005], [1, 2], Comparator(kind="float_tolerance", tolerance=1e-3), True),
        ([1.0, 2.01], [1, 2], Comparator(kind="float_tolerance", tolerance=1e-3), False),
        ("x", "x", Comparator(kind="float_tolerance", tolerance=1e-3), True),
    ],
)
def test_matches(output, expected, comparator, same) -> None:
    assert dsa.matches(output, expected, comparator) is same


# --- Results from a harness report ---


def test_one_test_per_case_with_messages() -> None:
    report = outputs(2, 5, None)
    report["cases"][2] = {"id": "c", "error": "ValueError: boom", "duration_ms": 3}

    result = dsa.results_from_run(program(report), CASES, IDS, None)

    assert result.status == "ok"
    assert [(t.id, t.outcome) for t in result.tests] == [
        ("a", "passed"),
        ("b", "failed"),
        ("c", "error"),
    ]
    assert result.tests[1].message == 'input {"x": 2}: expected 4, got 5'
    assert result.tests[2].message == 'input {"x": 3}: ValueError: boom'
    assert result.summary.model_dump() == {"passed": 1, "failed": 2, "total": 3}


@pytest.mark.parametrize(
    "report",
    [
        {"cases": outputs(2, 4)["cases"]},  # missing id
        {"cases": outputs(2, 4, 6)["cases"] + [{"id": "z", "output": 0}]},  # extra id
        {"cases": outputs(2, 4)["cases"] + [{"id": "a", "output": 2}]},  # duplicate id
    ],
    ids=["missing", "extra", "duplicate"],
)
def test_case_id_mismatch_is_an_error_not_passes(report) -> None:
    result = dsa.results_from_run(program(report), CASES, IDS, None)

    assert (result.status, result.reason, result.tests) == ("error", "test_set_mismatch", [])


@pytest.mark.parametrize("status", ["timeout", "oom", "error"])
def test_sandbox_failure_passes_nothing(status) -> None:
    result = dsa.results_from_run(program(None, status=status), CASES, IDS, None)
    assert (result.status, result.tests) == (status, [])


def test_fatal_load_error_is_reported() -> None:
    report = {"fatal": "could not load f from solution.py: SyntaxError: bad"}

    result = dsa.results_from_run(program(report), CASES, IDS, None)

    assert result.status == "error"
    assert "SyntaxError" in result.stderr_tail


# --- The harness script ---


def run_harness(tmp_path: Path, solution: str, cases: list[dict], timeout: str = "1") -> dict:
    (tmp_path / "solution.py").write_text(solution)
    (tmp_path / "inputs.json").write_text(json.dumps(cases))
    report = tmp_path / "report.json"
    subprocess.run(
        [
            sys.executable,
            "-I",
            str(HARNESS),
            "inputs.json",
            str(report),
            "solution.py",
            "f",
            timeout,
        ],
        cwd=tmp_path,
        check=True,
        timeout=30,
    )
    return json.loads(report.read_text())


def test_harness_calls_with_kwargs_args_or_a_value(tmp_path) -> None:
    solution = "def f(*args, **kwargs):\n    return [list(args), kwargs]\n"
    cases = [
        {"id": "kw", "input": {"s": "ab"}},
        {"id": "pos", "input": [1, 2]},
        {"id": "one", "input": 7},
    ]

    report = run_harness(tmp_path, solution, cases)

    assert [c["output"] for c in report["cases"]] == [[[], {"s": "ab"}], [[1, 2], {}], [[7], {}]]


def test_harness_times_out_per_case_and_carries_on(tmp_path) -> None:
    solution = (
        "def f(n):\n"
        "    while n < 0:\n"
        "        try:\n"
        "            pass\n"
        "        except Exception:\n"  # can't swallow the harness's timeout
        "            pass\n"
        "    return n\n"
    )
    cases = [{"id": "loop", "input": [-1]}, {"id": "ok", "input": [5]}]

    report = run_harness(tmp_path, solution, cases, timeout="0.2")

    assert report["cases"][0]["error"] == "timed out after 0.2 s"
    assert report["cases"][1]["output"] == 5


def test_harness_reports_errors_and_non_json_outputs(tmp_path) -> None:
    solution = "def f(x):\n    if x == 0:\n        raise KeyError('k')\n    return {1, 2}\n"

    report = run_harness(tmp_path, solution, [{"id": "a", "input": 0}, {"id": "b", "input": 1}])

    assert report["cases"][0]["error"] == "KeyError: 'k'"
    assert report["cases"][1]["error"].startswith("TypeError")


def test_harness_reports_a_function_that_cannot_load(tmp_path) -> None:
    report = run_harness(tmp_path, "def g(:\n", [{"id": "a", "input": 1}])
    assert report["fatal"].startswith("could not load f from solution.py: SyntaxError")
