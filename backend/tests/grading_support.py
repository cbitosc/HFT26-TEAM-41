"""A tiny task and a fake runner for grading tests that don't need Docker."""

import copy
import re
from typing import Any

from contracts_gen.run_result import RunResult, Summary, TestResult
from tests.api_support import LEAK_MARKER, domain_spec

FIXED = "def add(a, b):\n    return a + b\n"
BUGGY = "def add(a, b):\n    return a - b\n"


def tiny_spec() -> dict[str, Any]:
    spec = copy.deepcopy(domain_spec())
    spec.update(
        task_id="tiny-add",
        runtime="python311",
        starter_files={
            "app/__init__.py": "",
            "app/calc.py": BUGGY,
            "pytest.ini": "[pytest]\n",
            "tests/conftest.py": "# fixtures from the seed\n",
        },
        visible_tests=[
            {
                "path": "tests/test_visible.py",
                "content": "def test_adds():\n    pass\n\n\ndef test_zero():\n    pass\n",
            }
        ],
        hidden_tests=[
            {
                "path": f"tests/test_hidden_{LEAK_MARKER}.py",
                "content": f"def test_secret_{LEAK_MARKER}():\n    pass\n",
            }
        ],
        visible_test_ids=["tests/test_visible.py::test_adds", "tests/test_visible.py::test_zero"],
        hidden_test_ids=[f"tests/test_hidden_{LEAK_MARKER}.py::test_secret_{LEAK_MARKER}"],
        target_symbols=["app/calc.py::add"],
        entry_symbols=["app/calc.py::add"],
        perf=None,
        dsa_cases=None,
        # Not gate-certified: scored over all tests (tests/test_scores_api.py covers f2p).
        fail_to_pass=None,
        pass_to_pass=None,
    )
    return spec


class FakeRunner:
    """Stands in for runner.run_tests. Every collected test passes iff app/calc.py is FIXED.

    Hidden output mentions the test ids, so a leak of hidden data shows up as LEAK_MARKER.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.extra_test = False

    def __call__(self, runtime, files, test_paths, timeout_s=30, readonly=frozenset()):
        self.calls.append({"files": dict(files), "test_paths": test_paths, "readonly": readonly})
        ids = [
            f"{path}::{name}"
            for path in test_paths
            for name in re.findall(r"^def (test_\w+)", files[path], re.M)
        ]
        if self.extra_test:
            ids.append("tests/test_visible.py::test_smuggled")
        outcome = "passed" if files.get("app/calc.py") == FIXED else "failed"
        tests = [
            TestResult(
                id=test_id,
                name=test_id.split("::")[-1],
                outcome=outcome,
                duration_ms=1,
                message=None if outcome == "passed" else f"{test_id} failed",
            )
            for test_id in ids
        ]
        passed = sum(t.outcome == "passed" for t in tests)
        return RunResult(
            status="ok",
            reason=None,
            duration_ms=5,
            tests=tests,
            summary=Summary(passed=passed, failed=len(tests) - passed, total=len(tests)),
            stdout_tail=f"ran {' '.join(ids)}",
            stderr_tail="",
        )
