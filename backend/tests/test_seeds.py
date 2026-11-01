"""Static checks on every seed repo: concepts.yaml is accurate and the app stays small."""

from pathlib import Path

import pytest

from runner import RUNTIMES
from tests.seeds_support import load_concepts, seed_dirs, symbol_exists

MAX_APP_FILES = 10
MAX_APP_LINES = 520  # 500 until P2.4 added bulk import (the perf-sensitive code)

SEEDS = [pytest.param(path, id=path.name) for path in seed_dirs()]


def test_there_is_at_least_one_seed() -> None:
    assert SEEDS


@pytest.mark.parametrize("seed_dir", SEEDS)
def test_concepts_yaml_is_well_formed(seed_dir: Path) -> None:
    concepts = load_concepts(seed_dir)

    assert concepts["seed"] == seed_dir.name
    assert concepts["runtime"] in RUNTIMES
    assert concepts["concepts"]
    for name, concept in concepts["concepts"].items():
        assert concept["symbols"], f"{name} lists no symbols"
        assert concept["tests"], f"{name} lists no tests"


@pytest.mark.parametrize("seed_dir", SEEDS)
def test_every_listed_symbol_and_test_exists(seed_dir: Path) -> None:
    concepts = load_concepts(seed_dir)["concepts"]
    refs = [ref for concept in concepts.values() for ref in concept["symbols"] + concept["tests"]]

    missing = [ref for ref in refs if not symbol_exists(seed_dir, ref)]

    assert missing == []


@pytest.mark.parametrize("seed_dir", SEEDS)
def test_app_code_is_within_size_limits(seed_dir: Path) -> None:
    app_files = [
        path for path in seed_dir.rglob("*.py") if "tests" not in path.relative_to(seed_dir).parts
    ]
    lines = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in app_files)

    assert len(app_files) <= MAX_APP_FILES
    assert lines <= MAX_APP_LINES


def test_symbol_lookup_rejects_missing_names(tmp_path: Path) -> None:
    source = "class Cache:\n    def get(self):\n        pass\n\n\nLIMIT = 3\n"
    (tmp_path / "mod.py").write_text(source)

    assert symbol_exists(tmp_path, "mod.py::Cache.get")
    assert symbol_exists(tmp_path, "mod.py::LIMIT")
    assert not symbol_exists(tmp_path, "mod.py::Cache.put")
    assert not symbol_exists(tmp_path, "mod.py::missing")
    assert not symbol_exists(tmp_path, "nope.py::Cache")
