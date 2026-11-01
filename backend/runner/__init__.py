"""Runs candidate code in locked-down containers: test suites (run_tests -> RunResult) or
any command that writes a JSON report (run_program, used by the DSA harness)."""

from runner.runtimes import RUNTIMES
from runner.sandbox import ProgramRun, RunnerError, run_program, run_tests

__all__ = ["RUNTIMES", "ProgramRun", "RunnerError", "run_program", "run_tests"]
