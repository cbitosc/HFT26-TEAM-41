"""Every seed's own test suite must pass in its runtime sandbox. Run with `make test-docker`."""

from pathlib import Path

import pytest

from runner import run_tests
from tests.seeds_support import load_concepts, seed_dirs, seed_files

pytestmark = pytest.mark.docker


@pytest.mark.parametrize("seed_dir", [pytest.param(p, id=p.name) for p in seed_dirs()])
def test_seed_test_suite_passes_in_sandbox(seed_dir: Path) -> None:
    runtime = load_concepts(seed_dir)["runtime"]

    result = run_tests(runtime, seed_files(seed_dir), ["tests"], timeout_s=120)

    assert result.status == "ok", result.stdout_tail + result.stderr_tail
    assert result.summary.failed == 0
    assert result.summary.passed == result.summary.total > 0
