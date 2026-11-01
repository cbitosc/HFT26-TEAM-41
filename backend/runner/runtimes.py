"""Per-runtime details: image, test command, and how to read its JSON report."""

import posixpath
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from contracts_gen.run_result import TestResult

WORKSPACE = "/workspace"
OUT_DIR = "/runner-out"
"""Report and exit code go here, outside the workspace, under random names per run."""
MESSAGE_LIMIT = 2000

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class Runtime:
    image: str
    test_command: Callable[[list[str], set[str], str], list[str]]
    """(test paths, paths of the files in the workspace, JSON report path) -> command."""
    parse_report: Callable[[dict[str, Any]], list[TestResult]]
    ran_cleanly: Callable[[int, dict[str, Any]], bool]
    """False when tests couldn't be collected or the runner crashed (status "error")."""


def _message(text: str | None) -> str | None:
    if not text:
        return None
    return _ANSI.sub("", text)[:MESSAGE_LIMIT]


# --- Python: pytest + pytest-json-report -------------------------------------------------

_PYTEST_OUTCOMES = {
    "passed": "passed",
    "failed": "failed",
    "error": "error",
    "skipped": "skipped",
    "xfailed": "skipped",
    "xpassed": "passed",
}


def _pytest_command(test_paths: list[str], files: set[str], report_path: str) -> list[str]:
    return [
        "python",
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "-q",
        "--json-report",
        f"--json-report-file={report_path}",
        *test_paths,
    ]


def _pytest_message(test: dict[str, Any], outcome: str) -> str | None:
    phases = [test.get(name) or {} for name in ("setup", "call", "teardown")]
    if outcome in ("failed", "error"):
        for phase in phases:
            if phase.get("outcome") == "failed":
                crash = phase.get("crash") or {}
                return _message(crash.get("message") or str(phase.get("longrepr") or ""))
    if outcome == "skipped":
        for phase in phases:
            if phase.get("outcome") == "skipped":
                return _message(str(phase.get("longrepr") or ""))
    return None


def _parse_pytest(report: dict[str, Any]) -> list[TestResult]:
    results = []
    for test in report.get("tests", []):
        outcome = _PYTEST_OUTCOMES.get(test.get("outcome", ""), "error")
        seconds = sum(
            (test.get(phase) or {}).get("duration", 0) for phase in ("setup", "call", "teardown")
        )
        results.append(
            TestResult(
                id=test["nodeid"],
                name=test["nodeid"].split("::", 1)[-1],
                outcome=outcome,
                duration_ms=round(seconds * 1000),
                message=_pytest_message(test, outcome),
            )
        )
    return results


def _pytest_ran_cleanly(exit_code: int, report: dict[str, Any]) -> bool:
    # 0: all passed, 1: some failed. 2-5: interrupted, internal/usage error, nothing collected.
    return exit_code in (0, 1)


# --- Node: jest --json -------------------------------------------------------------------

_JEST_OUTCOMES = {"passed": "passed", "failed": "failed"}  # pending/skipped/todo/disabled


JEST_CONFIG_FILES = {
    "package.json",
    *(f"jest.config.{ext}" for ext in ("js", "ts", "mjs", "mts", "cjs", "cts", "json")),
}


def _jest_command(test_paths: list[str], files: set[str], report_path: str) -> list[str]:
    # Jest refuses to run without a config; use the repo's own when it has one.
    config = [] if files & JEST_CONFIG_FILES else [f'--config={{"rootDir": "{WORKSPACE}"}}']
    return [
        "jest",
        "--ci",
        "--json",
        f"--outputFile={report_path}",
        "--runInBand",
        "--no-cache",
        "--watchman=false",
        f"--rootDir={WORKSPACE}",
        *config,
        "--runTestsByPath",
        *test_paths,
    ]


def _parse_jest(report: dict[str, Any]) -> list[TestResult]:
    results = []
    for suite in report.get("testResults", []):
        path = posixpath.relpath(suite["name"], WORKSPACE)
        for test in suite.get("assertionResults", []):
            full_name = test.get("fullName") or test.get("title", "")
            results.append(
                TestResult(
                    id=f"{path}::{full_name}",
                    name=full_name,
                    outcome=_JEST_OUTCOMES.get(test.get("status", ""), "skipped"),
                    duration_ms=round(test.get("duration") or 0),
                    message=_message("\n".join(test.get("failureMessages") or [])),
                )
            )
    return results


def _jest_ran_cleanly(exit_code: int, report: dict[str, Any]) -> bool:
    # A suite that fails to load (syntax error, bad import) counts as a runtime error.
    return exit_code in (0, 1) and report.get("numRuntimeErrorTestSuites", 0) == 0


RUNTIMES: dict[str, Runtime] = {
    "python311": Runtime(
        image="assess-python311",
        test_command=_pytest_command,
        parse_report=_parse_pytest,
        ran_cleanly=_pytest_ran_cleanly,
    ),
    "node20": Runtime(
        image="assess-node20",
        test_command=_jest_command,
        parse_report=_parse_jest,
        ran_cleanly=_jest_ran_cleanly,
    ),
}
