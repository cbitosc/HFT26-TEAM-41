"""Helpers for the seed tests: find seeds, read their files, resolve concepts.yaml refs."""

import ast
from pathlib import Path

import yaml

from builder.seeds import SEEDS_DIR, seed_files

__all__ = ["SEEDS_DIR", "load_concepts", "seed_dirs", "seed_files", "symbol_exists"]


def seed_dirs() -> list[Path]:
    return sorted(path.parent for path in SEEDS_DIR.glob("*/concepts.yaml"))


def load_concepts(seed_dir: Path) -> dict:
    return yaml.safe_load((seed_dir / "concepts.yaml").read_text(encoding="utf-8"))


def symbol_exists(seed_dir: Path, ref: str) -> bool:
    """Whether "path.py::name" or "path.py::Class.method" is defined, checked without importing."""
    path, _, qualname = ref.partition("::")
    source = seed_dir / path
    if not qualname or not source.is_file():
        return False
    scope = ast.parse(source.read_text(encoding="utf-8")).body
    for name in qualname.split("."):
        node = next((node for node in scope if _defines(node, name)), None)
        if node is None:
            return False
        scope = getattr(node, "body", [])
    return True


def _defines(node: ast.stmt, name: str) -> bool:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return node.name == name
    if isinstance(node, ast.Assign):
        return any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id == name
    return False
