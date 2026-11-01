"""Shared data for the API tests: fixture task specs, including one full of leak markers."""

import copy
import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"

LEAK_MARKER = "LEAKMARKER"
LEAK_SEED = 987654321


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


def domain_spec() -> dict[str, Any]:
    return fixture("task_spec.valid.domain.json")


def dsa_spec() -> dict[str, Any]:
    return fixture("task_spec.valid.dsa.json")


def portfolio() -> dict[str, Any]:
    return fixture("portfolio.valid.json")


def leaky(spec: dict[str, Any]) -> dict[str, Any]:
    """Put a marker in every backend-only field, so a leak shows up as a substring."""
    spec = copy.deepcopy(spec)
    spec["reference_ref"] = f"{LEAK_MARKER}/reference"
    spec["target_symbols"] = [f"app/{LEAK_MARKER}.py::fix_me"]
    spec["random_seeds"] = [LEAK_SEED]
    spec["hidden_tests"] = [
        {"path": f"tests/test_{LEAK_MARKER}_hidden.py", "content": f"# {LEAK_MARKER} hidden"}
    ]
    if spec["dsa_cases"] is not None:
        spec["dsa_cases"]["hidden"] = [
            {"id": f"{LEAK_MARKER}-case", "input": {"s": LEAK_MARKER}, "expected": LEAK_MARKER}
        ]
    if spec["perf"] is not None:
        spec["perf"]["input_gen"] = f"{LEAK_MARKER}_gen"
    spec["certificate"]["scope_files"] = [f"app/{LEAK_MARKER}_scope.py"]
    return spec
