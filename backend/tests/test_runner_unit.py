"""Runner logic that needs no Docker: report parsing, path validation, output tails."""

import pytest

from runner.runtimes import RUNTIMES
from runner.sandbox import TAIL_BYTES, _tail, _validate_paths, _validate_test_paths


def test_pytest_report_is_mapped_to_test_results() -> None:
    report = {
        "exitcode": 1,
        "tests": [
            {
                "nodeid": "tests/test_a.py::test_ok",
                "outcome": "passed",
                "setup": {"duration": 0.001, "outcome": "passed"},
                "call": {"duration": 0.004, "outcome": "passed"},
                "teardown": {"duration": 0.001, "outcome": "passed"},
            },
            {
                "nodeid": "tests/test_a.py::TestCart::test_total",
                "outcome": "failed",
                "call": {
                    "duration": 0.02,
                    "outcome": "failed",
                    "crash": {"message": "AssertionError: assert 1 == 3"},
                },
            },
            {
                "nodeid": "tests/test_a.py::test_db",
                "outcome": "error",
                "setup": {
                    "duration": 0.01,
                    "outcome": "failed",
                    "crash": {"message": "fixture 'db' not found"},
                },
            },
            {"nodeid": "tests/test_a.py::test_later", "outcome": "xfailed"},
        ],
    }

    tests = RUNTIMES["python311"].parse_report(report)

    assert [(t.name, t.outcome, t.duration_ms) for t in tests] == [
        ("test_ok", "passed", 6),
        ("TestCart::test_total", "failed", 20),
        ("test_db", "error", 10),
        ("test_later", "skipped", 0),
    ]
    assert tests[0].message is None
    assert tests[1].message == "AssertionError: assert 1 == 3"
    assert tests[2].message == "fixture 'db' not found"


@pytest.mark.parametrize(("exit_code", "clean"), [(0, True), (1, True), (2, False), (5, False)])
def test_pytest_exit_codes(exit_code: int, clean: bool) -> None:
    assert RUNTIMES["python311"].ran_cleanly(exit_code, {}) is clean


def test_jest_report_is_mapped_to_test_results() -> None:
    report = {
        "numRuntimeErrorTestSuites": 0,
        "testResults": [
            {
                "name": "/workspace/src/sum.test.js",
                "assertionResults": [
                    {"fullName": "sum adds", "status": "passed", "duration": 3},
                    {
                        "fullName": "sum subtracts",
                        "status": "failed",
                        "duration": 5,
                        "failureMessages": ["\x1b[31mExpected: 1\x1b[39m\nReceived: 3"],
                    },
                    {"fullName": "sum later", "status": "todo", "duration": None},
                ],
            }
        ],
    }

    tests = RUNTIMES["node20"].parse_report(report)

    assert [(t.id, t.outcome) for t in tests] == [
        ("src/sum.test.js::sum adds", "passed"),
        ("src/sum.test.js::sum subtracts", "failed"),
        ("src/sum.test.js::sum later", "skipped"),
    ]
    assert tests[1].message == "Expected: 1\nReceived: 3"  # ANSI colour codes stripped


def test_jest_gets_a_default_config_only_when_the_repo_has_none() -> None:
    command = RUNTIMES["node20"].test_command

    bare_repo = command(["sum.test.js"], {"sum.js", "sum.test.js"}, "/runner-out/r.json")
    repo_with_config = command(
        ["sum.test.js"], {"package.json", "sum.test.js"}, "/runner-out/r.json"
    )

    assert any(arg.startswith("--config=") for arg in bare_repo)
    assert not any(arg.startswith("--config=") for arg in repo_with_config)


@pytest.mark.parametrize("runtime", ["python311", "node20"])
def test_report_goes_to_the_given_path(runtime: str) -> None:
    command = RUNTIMES[runtime].test_command(["test_x.py"], {"test_x.py"}, "/runner-out/abc.json")

    assert any(arg.endswith("=/runner-out/abc.json") for arg in command)
    assert not any("/workspace/.runner" in arg for arg in command)


def test_jest_suite_that_fails_to_load_is_not_clean() -> None:
    assert RUNTIMES["node20"].ran_cleanly(1, {"numRuntimeErrorTestSuites": 1}) is False


@pytest.mark.parametrize(
    "path",
    ["/etc/passwd", "../outside.py", "tests/../../x.py", ".runner/report.json", "a//b.py", ""],
)
def test_unsafe_file_paths_are_rejected(path: str) -> None:
    with pytest.raises(ValueError):
        _validate_paths({path: ""})


def test_test_path_cannot_be_a_cli_option() -> None:
    with pytest.raises(ValueError, match="command-line option"):
        _validate_test_paths(["-pevil"])


def test_tail_keeps_only_the_last_bytes() -> None:
    output = b"a" * 10_000 + b"END"

    tail = _tail(output)

    assert len(tail) == TAIL_BYTES
    assert tail.endswith("END")
