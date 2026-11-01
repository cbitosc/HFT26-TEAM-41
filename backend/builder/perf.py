"""Measuring perf tests in the sandbox (P2.4): used by Master calibration and by submit.

A perf test (seeds/<seed>/tests/perf/) times its workload and records the result with
pytest's `record_property("perf_ms", ms)`. RunResult has no room for it, so this reads the
raw pytest-json-report, whose tests carry their `user_properties`.
"""

import math
from dataclasses import dataclass

from contracts_gen.run_result import TestResult
from runner import RUNTIMES, run_program

PERF_PROPERTY = "perf_ms"
# Perf tests and their input generator: only Master tasks use them, always as hidden tests.
PERF_DIR = "tests/perf/"


@dataclass(frozen=True)
class PerfRun:
    status: str
    tests: list[TestResult]
    perf_ms: float | None
    """Slowest perf_ms recorded; the time limit if the run timed out; None if none recorded."""


def run_with_perf(
    runtime: str,
    files: dict[str, str],
    test_paths: list[str],
    timeout_s: int,
    readonly: frozenset[str] = frozenset(),
) -> PerfRun:
    spec = RUNTIMES[runtime]
    run = run_program(
        runtime,
        files,
        lambda report_path: spec.test_command(test_paths, set(files), report_path),
        timeout_s=timeout_s,
        readonly=readonly,
    )
    if run.status == "timeout":
        # Too slow to finish: the limit is a lower bound on its time.
        return PerfRun("timeout", [], timeout_s * 1000.0)
    report = run.report or {}
    tests = spec.parse_report(report) if run.report is not None else []
    status = run.status
    if status == "ok" and (run.report is None or not spec.ran_cleanly(run.exit_code, report)):
        status = "error"
    times = [
        value
        for test in report.get("tests", [])
        for prop in test.get("user_properties") or []
        if isinstance(prop, dict)
        and isinstance(value := prop.get(PERF_PROPERTY), int | float)
        and math.isfinite(value)
        and value >= 0
    ]
    return PerfRun(status, tests, float(max(times)) if times else None)
