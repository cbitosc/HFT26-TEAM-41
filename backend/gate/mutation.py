"""Optional mutation testing (off by default): mutmut on the reference, the hidden tests as the
test suite, in one sandbox. Score = killed mutants / all mutants (timeouts count as killed).

Takes 1-3 minutes per task, so the gate runs it only when asked (`make gate MUTATION=1`).
Python domain tasks only; DSA tasks have no pytest suite and stay "not measured".
"""

import logging
import shlex

from app.workspace import build_workspace, runnable_test_paths
from contracts_gen.task_spec import TaskSpec
from gate.limits import MUTATION_TIMEOUT_S
from runner import run_program

logger = logging.getLogger(__name__)

JUNIT_PATH = ".mutmut-junit.xml"
# junitxml -> {"tests": n, "failures": survived, ...} at the report path.
_TO_JSON = (
    "import json, sys, xml.etree.ElementTree as E; "
    "s = E.parse(sys.argv[1]).getroot().find('testsuite'); "
    "json.dump({k: int(s.get(k, 0)) for k in ('tests', 'failures', 'errors', 'skipped')}, "
    "open(sys.argv[2], 'w'))"
)


def mutation_score(
    spec: TaskSpec, reference: dict[str, str], scope_files: list[str]
) -> float | None:
    """Killed share of mutmut's mutants of `scope_files`; None if it can't be measured."""
    targets = [path for path in scope_files if path.endswith(".py")]
    tests = runnable_test_paths(spec.runtime, spec.hidden_tests)
    if spec.runtime != "python311" or not targets or not tests:
        return None
    files = build_workspace(spec, reference, spec.hidden_tests)
    runner = "python -m pytest -x -q -p no:cacheprovider " + " ".join(map(shlex.quote, tests))

    def command(report_path: str) -> list[str]:
        script = (
            f"python -m mutmut run --paths-to-mutate {shlex.quote(','.join(targets))} "
            f"--runner {shlex.quote(runner)} --no-progress >/dev/null 2>&1; "
            f"python -m mutmut junitxml > {JUNIT_PATH} && "
            f"python -c {shlex.quote(_TO_JSON)} {JUNIT_PATH} {shlex.quote(report_path)}"
        )
        return ["sh", "-c", script]

    run = run_program(spec.runtime, files, command, timeout_s=MUTATION_TIMEOUT_S)
    report = run.report or {}
    if run.status != "ok" or not report.get("tests"):
        logger.warning("mutation testing of %s gave no result: %s", spec.task_id, run.status)
        return None
    return round((report["tests"] - report["failures"]) / report["tests"], 4)
