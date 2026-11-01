"""The DSA taxonomy (dsa/taxonomy.yaml) and the seed concept vocabulary."""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from builder.seeds import DSA_DIR, SEEDS_DIR

TAXONOMY_PATH = DSA_DIR / "taxonomy.yaml"
TIERS = ("novice", "adept", "master")


@dataclass(frozen=True)
class TierRule:
    min_projects: int
    min_solved: int


@dataclass(frozen=True)
class Taxonomy:
    thresholds: dict[str, int]
    """Difficulty -> problems solved in a topic needed before it's allowed."""
    tier_difficulty: dict[str, str]
    tier_rules: dict[str, TierRule]
    topic_tiers: dict[str, tuple[str, ...]]
    """Canonical topic -> tiers that may use it, in file order."""
    aliases: dict[str, str]
    """Normalized name (canonical id or synonym) -> canonical topic."""

    def canonical(self, name: str) -> str | None:
        return self.aliases.get(normalize_topic(name))

    def threshold(self, tier: str) -> int:
        return self.thresholds[self.tier_difficulty[tier]]


def normalize_topic(name: str) -> str:
    """'Dynamic Programming' / 'dynamic-programming' / 'DP ' -> 'dynamic_programming' / 'dp'."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def parse_taxonomy(data: dict) -> Taxonomy:
    aliases: dict[str, str] = {}
    topic_tiers = {}
    for topic, entry in data["topics"].items():
        tiers = tuple(entry["tiers"])
        unknown = set(tiers) - set(TIERS)
        if unknown:
            raise ValueError(f"taxonomy topic {topic}: unknown tiers {sorted(unknown)}")
        topic_tiers[topic] = tiers
        for alias in [topic, *entry.get("synonyms", [])]:
            key = normalize_topic(alias)
            if aliases.get(key, topic) != topic:
                raise ValueError(f"taxonomy: {alias!r} maps to both {aliases[key]} and {topic}")
            aliases[key] = topic
    return Taxonomy(
        thresholds=dict(data["thresholds"]),
        tier_difficulty=dict(data["tier_difficulty"]),
        tier_rules={tier: TierRule(**rule) for tier, rule in data["tier_rules"].items()},
        topic_tiers=topic_tiers,
        aliases=aliases,
    )


@lru_cache
def load_taxonomy(path: Path = TAXONOMY_PATH) -> Taxonomy:
    return parse_taxonomy(yaml.safe_load(path.read_text(encoding="utf-8")))


@lru_cache
def concept_vocabulary(seeds_dir: Path = SEEDS_DIR) -> tuple[str, ...]:
    """Union of the concepts in seeds/*/concepts.yaml, sorted."""
    concepts: set[str] = set()
    for path in seeds_dir.glob("*/concepts.yaml"):
        concepts |= set(yaml.safe_load(path.read_text(encoding="utf-8"))["concepts"])
    return tuple(sorted(concepts))
