"""What a candidate may edit, and how the files for a test run are put together.

Editable = a path in the task's starter_files that is not protected. Protected paths
(tests, test config, import hooks, package manifests) always come from the backend, so a
candidate can't change which tests run or how they are reported.
"""

import posixpath
import re

from contracts_gen.task_spec import TaskSpec, TestFile

TEST_DIRS = {"tests", "test", "__tests__"}
PROTECTED_NAMES = {
    # Python test config and import hooks
    "conftest.py",
    "pytest.ini",
    "tox.ini",
    "setup.cfg",
    "pyproject.toml",
    "sitecustomize.py",
    "usercustomize.py",
    # Node test config and package manifests
    "package.json",
    ".npmrc",
    ".babelrc",
}
PROTECTED_PATTERNS = [
    re.compile(r".*\.pth"),
    re.compile(r"jest\.config\..*"),
    re.compile(r"\.babelrc\..*"),
    re.compile(r"babel\.config\..*"),
]
# Test modules, by runner naming convention.
TEST_FILE_PATTERNS = {
    "python311": re.compile(r"(test_.*|.*_test)\.py"),
    "node20": re.compile(r".*\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)"),
}


def protected_reason(path: str) -> str | None:
    """Why `path` can never be edited by a candidate, or None."""
    parts = path.lower().split("/")
    name = parts[-1]
    if TEST_DIRS & set(parts[:-1]):
        return "test directories are read-only"
    if name in PROTECTED_NAMES or any(p.fullmatch(name) for p in PROTECTED_PATTERNS):
        return f"{name} is test or package configuration"
    if any(p.fullmatch(name) for p in TEST_FILE_PATTERNS.values()):
        return "test files are read-only"
    return None


def not_editable_reason(spec: TaskSpec, path: str) -> str | None:
    reason = protected_reason(path)
    if reason is None and path not in spec.starter_files:
        reason = "only files in the task's starter code can be edited"
    return reason


def split_editable(spec: TaskSpec, files: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """(editable files, sorted list of dropped paths)."""
    kept = {p: c for p, c in files.items() if not_editable_reason(spec, p) is None}
    return kept, sorted(set(files) - set(kept))


def build_workspace(
    spec: TaskSpec, candidate_files: dict[str, str], tests: list[TestFile]
) -> dict[str, str]:
    """Starter files, then the candidate's editable files, then `tests` over the top."""
    editable, _ = split_editable(spec, candidate_files)
    return {
        **spec.starter_files,
        **editable,
        **{test.path: test.content for test in tests},
    }


def runnable_test_paths(runtime: str, tests: list[TestFile]) -> list[str]:
    """The test files to hand to the runner. Others (data, cases JSON) are only copied."""
    pattern = TEST_FILE_PATTERNS[runtime]
    return sorted(t.path for t in tests if pattern.fullmatch(posixpath.basename(t.path)))


def changed_files(spec: TaskSpec, candidate_files: dict[str, str]) -> dict[str, str]:
    """The candidate's editable files that differ from the starter."""
    editable, _ = split_editable(spec, candidate_files)
    return {p: c for p, c in editable.items() if spec.starter_files.get(p) != c}
