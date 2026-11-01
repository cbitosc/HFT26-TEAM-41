"""Editable allowlist and workspace assembly (anti-tampering rule 4a)."""

import pytest

from app.workspace import (
    build_workspace,
    not_editable_reason,
    protected_reason,
    runnable_test_paths,
    split_editable,
)
from contracts_gen.task_spec import TaskSpec
from contracts_gen.task_spec import TestFile as SpecTestFile
from tests.grading_support import tiny_spec


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_x.py",
        "tests/helpers.py",
        "src/__tests__/a.js",
        "conftest.py",
        "app/conftest.py",
        "pytest.ini",
        "tox.ini",
        "setup.cfg",
        "pyproject.toml",
        "sitecustomize.py",
        "usercustomize.py",
        "evil.pth",
        "test_root.py",
        "app/calc_test.py",
        "package.json",
        "jest.config.js",
        "jest.config.ts",
        ".babelrc",
        "babel.config.js",
        ".npmrc",
        "src/sum.test.js",
        "src/sum.spec.ts",
        "Tests/test_x.py",
    ],
)
def test_protected_paths(path: str) -> None:
    assert protected_reason(path) is not None


@pytest.mark.parametrize(
    "path", ["app/calc.py", "app/testing_utils.py", "solution.py", "src/contest.js", "README.md"]
)
def test_ordinary_paths_are_not_protected(path: str) -> None:
    assert protected_reason(path) is None


def test_only_unprotected_starter_files_are_editable() -> None:
    spec = TaskSpec.model_validate(tiny_spec())

    assert not_editable_reason(spec, "app/calc.py") is None
    # In the starter, but protected.
    assert not_editable_reason(spec, "pytest.ini") is not None
    assert not_editable_reason(spec, "tests/conftest.py") is not None
    # Not in the starter.
    assert "starter" in not_editable_reason(spec, "app/new.py")


def test_split_drops_everything_not_editable() -> None:
    spec = TaskSpec.model_validate(tiny_spec())
    files = {"app/calc.py": "x", "conftest.py": "y", "tests/test_visible.py": "z", "app/new.py": ""}

    kept, dropped = split_editable(spec, files)

    assert kept == {"app/calc.py": "x"}
    assert dropped == ["app/new.py", "conftest.py", "tests/test_visible.py"]


def test_workspace_order_is_starter_then_candidate_then_backend_tests() -> None:
    spec = TaskSpec.model_validate(tiny_spec())
    candidate = {
        "app/calc.py": "def add(a, b):\n    return a + b\n",
        "tests/conftest.py": "FORCE_PASS = True\n",
        "tests/test_visible.py": "def test_one():\n    pass\n",
    }

    files = build_workspace(spec, candidate, spec.visible_tests)

    assert files["app/calc.py"] == candidate["app/calc.py"]
    assert files["tests/conftest.py"] == spec.starter_files["tests/conftest.py"]
    assert files["tests/test_visible.py"] == spec.visible_tests[0].content
    assert not any(t.path in files for t in spec.hidden_tests)


def test_runnable_test_paths_skip_data_files() -> None:
    tests = [
        SpecTestFile(path="tests/test_cases.py", content=""),
        SpecTestFile(path="tests/cases_hidden.json", content="[]"),
        SpecTestFile(path="tests/conftest.py", content=""),
    ]
    assert runnable_test_paths("python311", tests) == ["tests/test_cases.py"]
