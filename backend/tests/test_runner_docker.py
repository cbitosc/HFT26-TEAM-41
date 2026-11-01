"""Runner tests against real sandbox containers. Run with `make test-docker` (in the worker,
which has the Docker socket) after `make runtimes`."""

import dataclasses
import time

import docker
import pytest

from runner import RunnerError, run_tests
from runner.runtimes import RUNTIMES

pytestmark = pytest.mark.docker


@pytest.fixture(autouse=True)
def no_leftover_sandboxes():
    """Every run must remove its container and volume, whatever happened."""
    yield
    client = docker.from_env()
    containers = client.containers.list(all=True, filters={"label": "assess.runner"})
    volumes = client.volumes.list(filters={"label": "assess.runner"})
    assert containers == [] and volumes == []


def test_passing_python_tests() -> None:
    files = {
        "test_math.py": (
            "def test_add():\n    assert 1 + 1 == 2\n\n\ndef test_mul():\n    assert 2 * 3 == 6\n"
        )
    }

    result = run_tests("python311", files, ["test_math.py"])

    assert result.status == "ok"
    assert result.summary.model_dump() == {"passed": 2, "failed": 0, "total": 2}
    assert {t.id for t in result.tests} == {"test_math.py::test_add", "test_math.py::test_mul"}


def test_failing_assertion_is_reported_with_its_message() -> None:
    files = {
        "conftest.py": "",
        "calc.py": "def add(a, b):\n    return a - b\n",
        "tests/test_calc.py": (
            "from calc import add\n\n\n"
            "def test_add():\n    assert add(2, 1) == 3\n\n\n"
            "def test_truth():\n    assert True\n"
        ),
    }

    result = run_tests("python311", files, ["tests"])

    assert result.status == "ok"
    assert result.summary.model_dump() == {"passed": 1, "failed": 1, "total": 2}
    failed = next(t for t in result.tests if t.outcome == "failed")
    assert failed.id == "tests/test_calc.py::test_add"
    assert "assert 1 == 3" in failed.message


def test_infinite_loop_times_out() -> None:
    files = {"test_loop.py": "def test_forever():\n    while True:\n        pass\n"}

    started = time.monotonic()
    result = run_tests("python311", files, ["test_loop.py"], timeout_s=5)
    elapsed = time.monotonic() - started

    assert result.status == "timeout"
    assert elapsed < 5 + 5


def test_network_is_blocked() -> None:
    files = {
        "test_net.py": (
            "import urllib.request\n\n\n"
            "def test_fetch():\n"
            '    urllib.request.urlopen("http://1.1.1.1", timeout=5)\n'
        )
    }

    result = run_tests("python311", files, ["test_net.py"])

    assert result.status == "ok"
    assert result.summary.failed == 1
    assert "Network is unreachable" in result.tests[0].message


def test_allocating_2gb_is_oom_killed() -> None:
    # b"x" * n writes every byte; bytearray(n) would only reserve untouched zero pages.
    files = {"test_mem.py": 'def test_alloc():\n    data = b"x" * (2 * 1024**3)\n    assert data\n'}

    result = run_tests("python311", files, ["test_mem.py"])

    assert result.status == "oom"


def test_sandbox_is_locked_down() -> None:
    files = {
        "test_sandbox.py": (
            "import os\n\nimport pytest\n\n\n"
            "def test_not_root():\n    assert os.getuid() == 10001\n\n\n"
            "def test_root_filesystem_is_read_only():\n"
            "    with pytest.raises(OSError):\n"
            '        open("/etc/escape", "w")\n\n\n'
            "def test_workspace_is_writable():\n"
            '    with open("/workspace/scratch.txt", "w") as f:\n'
            '        f.write("ok")\n'
        )
    }

    result = run_tests("python311", files, ["test_sandbox.py"])

    assert result.status == "ok"
    assert result.summary.model_dump() == {"passed": 3, "failed": 0, "total": 3}


def test_readonly_files_and_report_are_out_of_reach() -> None:
    files = {
        "data.txt": "original",
        "test_tamper.py": (
            "import os\n\nimport pytest\n\n\n"
            "def test_readonly_file_cannot_be_edited():\n"
            "    with pytest.raises(PermissionError):\n"
            '        open("/workspace/data.txt", "w")\n\n\n'
            "def test_no_report_or_exit_code_in_the_workspace():\n"
            '    assert sorted(os.listdir("/workspace/.runner")) == ["go", "home", "tmp"]\n'
        ),
    }

    result = run_tests("python311", files, ["test_tamper.py"], readonly=frozenset({"data.txt"}))

    assert result.status == "ok", result.stdout_tail
    assert result.summary.model_dump() == {"passed": 2, "failed": 0, "total": 2}


def test_protected_test_files_cannot_be_deleted_replaced_or_added() -> None:
    attempts = {
        "delete": 'os.remove("/workspace/tests/test_other.py")',
        "rename_file": 'os.rename("/workspace/tests/test_other.py", "/workspace/tests/x.py")',
        "rename_dir": 'os.rename("/workspace/tests", "/workspace/tests_old")',
        "replace_dir": 'shutil.rmtree("/workspace/tests")',
        "add_conftest": 'open("/workspace/tests/conftest.py", "w")',
        "add_at_root": 'open("/workspace/conftest.py", "w")',
        "edit_config": 'open("/workspace/pytest.ini", "a")',
    }
    body = "".join(
        f"def test_cannot_{name}():\n    with pytest.raises(PermissionError):\n        {code}\n\n\n"
        for name, code in attempts.items()
    )
    body += (
        "def test_code_dirs_stay_writable():\n"
        '    with open("/workspace/app/scratch.txt", "w") as f:\n'
        '        f.write("ok")\n'
    )
    files = {
        "pytest.ini": "[pytest]\n",
        "app/calc.py": "X = 1\n",
        "tests/test_other.py": "def test_other():\n    pass\n",
        "tests/test_tamper.py": "import os\nimport shutil\n\nimport pytest\n\n\n" + body,
    }
    readonly = frozenset({"pytest.ini", "tests/test_other.py", "tests/test_tamper.py"})

    result = run_tests("python311", files, ["tests/test_tamper.py"], readonly=readonly)

    assert result.status == "ok", result.stdout_tail
    failed = [t.id for t in result.tests if t.outcome != "passed"]
    assert failed == [], [t.message for t in result.tests if t.outcome != "passed"]
    assert result.summary.total == len(attempts) + 1


def test_collection_error_is_status_error() -> None:
    files = {"test_broken.py": "def test_x(:\n    pass\n"}

    result = run_tests("python311", files, ["test_broken.py"])

    assert result.status == "error"
    assert "SyntaxError" in result.stdout_tail


def test_passing_jest_test() -> None:
    files = {
        "sum.js": "module.exports = (a, b) => a + b;\n",
        "sum.test.js": (
            "const sum = require('./sum');\n\n"
            "test('adds two numbers', () => {\n  expect(sum(1, 2)).toBe(3);\n});\n"
        ),
    }

    result = run_tests("node20", files, ["sum.test.js"])

    assert result.status == "ok"
    assert result.summary.model_dump() == {"passed": 1, "failed": 0, "total": 1}
    assert result.tests[0].id == "sum.test.js::adds two numbers"


def test_missing_image_raises_and_cleans_up(monkeypatch) -> None:
    broken = dataclasses.replace(RUNTIMES["python311"], image="assess-does-not-exist")
    monkeypatch.setitem(RUNTIMES, "python311", broken)

    with pytest.raises(RunnerError, match="make runtimes"):
        run_tests("python311", {"test_x.py": "def test_x():\n    pass\n"}, ["test_x.py"])
