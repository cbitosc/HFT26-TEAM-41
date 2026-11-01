"""Locating seed repos and DSA bank entries, and reading their files."""

from pathlib import Path

# backend/builder/ -> repo root. In the containers this resolves to / (/seeds, /dsa).
REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDS_DIR = REPO_ROOT / "seeds"
DSA_DIR = REPO_ROOT / "dsa"
SKIPPED_DIRS = {"__pycache__", ".pytest_cache", ".hypothesis"}


def seed_files(seed_dir: Path) -> dict[str, str]:
    """Every file in the seed, keyed by its path relative to the seed root."""
    return {
        path.relative_to(seed_dir).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(seed_dir.rglob("*"))
        if path.is_file() and not SKIPPED_DIRS & set(path.relative_to(seed_dir).parts)
    }
