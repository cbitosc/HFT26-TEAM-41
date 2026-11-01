"""Portfolio -> Profile, by deterministic keyword rules (keywords.py, dsa/taxonomy.yaml).

One LLM call (generator slot) is made only when the rules find no domain or no concept;
its answers are restricted to the allowed values and fill only the fields the rules left
empty. Same portfolio, same profile: the rules are pure and the LLM call is cached.
"""

import logging
import re
from collections.abc import Callable
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

from contracts_gen.portfolio import Portfolio
from contracts_gen.profile import AllowedTopics, Profile, Sources
from llm import complete_structured
from profiler import keywords
from profiler.taxonomy import TIERS, Taxonomy, concept_vocabulary, load_taxonomy

logger = logging.getLogger(__name__)

# Evidence weights: a project's keywords are its stack (portfolio schema), skills come
# next, prose (labels, summaries, descriptions, highlights) counts least.
PROJECT_KEYWORD_WEIGHT = 3
SKILL_WEIGHT = 2
PROSE_WEIGHT = 1

LLM_MAX_TOKENS = 150
LLM_PROMPT_CHARS = 1500
LLM_MAX_CONCEPTS = 5

Llm = Callable[..., BaseModel]


class Evidence:
    """Weighted portfolio text that keyword terms are counted in."""

    def __init__(self, portfolio: Portfolio) -> None:
        self.items: list[tuple[str, int]] = []  # whole stack items, lowercased
        self.texts: list[tuple[str, int]] = []
        for project in portfolio.projects or []:
            for keyword in project.keywords or []:
                self.items.append((keyword.strip().lower(), PROJECT_KEYWORD_WEIGHT))
            prose = [project.name, project.description, *(project.highlights or [])]
            self.texts += [(text, PROSE_WEIGHT) for text in prose if text]
        for skill in portfolio.skills or []:
            for name in [skill.name, *(skill.keywords or [])]:
                if name:
                    self.items.append((name.strip().lower(), SKILL_WEIGHT))
        basics = portfolio.basics
        self.texts += [(text, PROSE_WEIGHT) for text in (basics.label, basics.summary) if text]
        self.texts = [(text.lower(), weight) for text, weight in self.texts]

    def score(self, terms: list[str]) -> int:
        total = 0
        for term in terms:
            if term.startswith("="):
                total += sum(w for item, w in self.items if item == term[1:])
                continue
            pattern = _pattern(term)
            for text, weight in [*self.items, *self.texts]:
                total += weight * len(pattern.findall(text))
        return total

    def best(self, options: dict[str, list[str]]) -> tuple[str | None, dict[str, int]]:
        """The option with the highest score (ties: first in `options`), or None if all 0."""
        scores = {name: self.score(terms) for name, terms in options.items()}
        top = max(scores.values(), default=0)
        best = next((name for name, s in scores.items() if s == top), None) if top else None
        return best, scores


@lru_cache(maxsize=512)
def _pattern(term: str) -> re.Pattern[str]:
    prefix = term.endswith("*")
    body = re.escape(term.rstrip("*").lower())
    return re.compile(rf"(?<![a-z0-9]){body}" + ("" if prefix else r"(?![a-z0-9])"))


def build_profile(
    portfolio: dict[str, Any],
    llm: Llm = complete_structured,
    taxonomy: Taxonomy | None = None,
    vocabulary: tuple[str, ...] | None = None,
) -> Profile:
    taxonomy = taxonomy or load_taxonomy()
    vocabulary = vocabulary if vocabulary is not None else concept_vocabulary()
    parsed = Portfolio.model_validate(portfolio)
    evidence = Evidence(parsed)
    notes: list[str] = []
    sources = {"domain": "rules", "runtime": "rules", "concepts": "rules"}

    domain, _ = evidence.best(keywords.DOMAINS)
    concepts = _concepts(evidence, vocabulary)
    runtime, _ = evidence.best(keywords.RUNTIMES)
    unsupported = [
        label for label, terms in keywords.UNSUPPORTED_STACKS.items() if evidence.score(terms)
    ]

    guess = None
    if domain is None or not concepts:
        guess = _llm_guess(parsed, vocabulary, llm, notes)
    if domain is None:
        domain, sources["domain"] = (guess.domain, "llm") if guess else ("backend", "default")
    if not concepts:
        concepts, sources["concepts"] = (list(guess.concepts), "llm") if guess else ([], "default")
    if runtime is None:
        if unsupported:
            runtime = keywords.CLOSEST_RUNTIME[domain]
        elif guess:
            runtime, sources["runtime"] = guess.runtime, "llm"
        else:
            runtime, sources["runtime"] = keywords.CLOSEST_RUNTIME[domain], "default"
            notes.append(f"No supported stack recognised; the domain task uses {runtime}.")
    notes += [
        f"{label} is not a supported runtime; the domain task uses {runtime}."
        for label in unsupported
    ]

    topics_solved = _topics_solved(parsed, taxonomy, notes)
    allowed = {tier: _allowed_topics(topics_solved, taxonomy, tier) for tier in TIERS}
    if not allowed["novice"]:
        notes.append("No solved DSA topic from the taxonomy; no DSA topic is allowed.")
    tier, reason = _suggest_tier(topics_solved, len(parsed.projects or []), allowed, taxonomy)

    return Profile(
        domain=domain,
        runtime=runtime,
        concepts=concepts,
        topics_solved=topics_solved,
        allowed_topics=AllowedTopics(**allowed),
        suggested_tier=tier,
        tier_reason=reason,
        unsupported_notes=notes,
        sources=Sources(**sources),
    )


def _concepts(evidence: Evidence, vocabulary: tuple[str, ...]) -> list[str]:
    """Vocabulary concepts with evidence, strongest first (ties by name)."""
    scores = {
        concept: evidence.score([concept, *keywords.CONCEPTS.get(concept, [])])
        for concept in vocabulary
    }
    found = [concept for concept, score in scores.items() if score > 0]
    return sorted(found, key=lambda concept: (-scores[concept], concept))


def _topics_solved(portfolio: Portfolio, taxonomy: Taxonomy, notes: list[str]) -> dict[str, int]:
    """Claimed topic names -> canonical topics; counts of synonyms are summed."""
    solved: dict[str, int] = {}
    claimed = portfolio.assessment.dsaTopicsSolved or {}
    for name, count in sorted(claimed.items()):
        topic = taxonomy.canonical(name)
        if topic is None:
            notes.append(f"DSA topic {name!r} is not in the taxonomy; ignored.")
            continue
        solved[topic] = solved.get(topic, 0) + count.root
    return dict(sorted(solved.items()))


def _allowed_topics(solved: dict[str, int], taxonomy: Taxonomy, tier: str) -> list[str]:
    """Topics listed for the tier and solved at least its threshold, most solved first."""
    threshold = taxonomy.threshold(tier)
    allowed = [
        topic
        for topic, count in solved.items()
        if count >= threshold and tier in taxonomy.topic_tiers[topic]
    ]
    return sorted(allowed, key=lambda topic: (-solved[topic], topic))


def _suggest_tier(
    solved: dict[str, int], projects: int, allowed: dict[str, list[str]], taxonomy: Taxonomy
) -> tuple[str, str]:
    total = sum(solved.values())
    facts = (
        f"{_count(total, 'problem')} solved in {_count(len(solved), 'taxonomy topic')}, "
        f"{_count(projects, 'project')}"
    )
    for tier in ("master", "adept"):
        rule = taxonomy.tier_rules[tier]
        need = (
            f"≥{rule.min_projects} projects, ≥{rule.min_solved} solved, "
            f"≥1 topic with ≥{taxonomy.threshold(tier)} solved"
        )
        if projects >= rule.min_projects and total >= rule.min_solved and allowed[tier]:
            return tier, f"{facts}: meets the {tier} rule ({need})."
    rule = taxonomy.tier_rules["adept"]
    return "novice", (
        f"{facts}: below the adept rule (≥{rule.min_projects} projects, "
        f"≥{rule.min_solved} solved, ≥1 topic with ≥{taxonomy.threshold('adept')} solved)."
    )


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


# --- LLM fallback -----------------------------------------------------------------------


def _guess_model(vocabulary: tuple[str, ...]) -> type[BaseModel]:
    concept = Literal[vocabulary] if vocabulary else Literal["none"]  # type: ignore[valid-type]
    return create_model(
        "ProfileGuess",
        domain=(Literal["backend", "web", "ml", "security"], ...),
        runtime=(Literal["python311", "node20"], ...),
        concepts=(list[concept], Field(max_length=LLM_MAX_CONCEPTS)),
    )


def _llm_guess(
    portfolio: Portfolio, vocabulary: tuple[str, ...], llm: Llm, notes: list[str]
) -> BaseModel | None:
    """One generator call; None (with a note) if it fails, e.g. over budget."""
    system = (
        "Classify a developer portfolio. Use only the allowed values. "
        "domain: backend | web | ml | security. "
        "runtime: python311 (Python) or node20 (JavaScript/TypeScript), the closer one. "
        f"concepts: up to {LLM_MAX_CONCEPTS} of [{', '.join(vocabulary)}] the portfolio shows "
        "hands-on experience with; [] if none. Reply with JSON only."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": _portfolio_text(portfolio)},
    ]
    try:
        guess = llm(
            "generator",
            messages,
            _guess_model(vocabulary),
            temperature=0,
            max_retries=1,
            max_tokens=LLM_MAX_TOKENS,
        )
    except Exception as exc:
        logger.warning("profiler LLM fallback failed: %s", exc)
        notes.append("The rules found too little and the LLM fallback failed; defaults used.")
        return None
    guess.concepts = [c for c in guess.concepts if c in vocabulary]
    return guess


def _portfolio_text(portfolio: Portfolio) -> str:
    """The portfolio's descriptive fields only, truncated (token policy)."""
    lines = [portfolio.basics.label or "", portfolio.basics.summary or ""]
    for skill in portfolio.skills or []:
        lines.append(f"Skill {skill.name or ''}: {', '.join(skill.keywords or [])}")
    for project in portfolio.projects or []:
        stack = ", ".join(project.keywords or [])
        lines.append(f"Project {project.name or ''}: {project.description or ''} [{stack}]")
        lines += project.highlights or []
    text = "\n".join(line.strip() for line in lines if line.strip())
    return text[:LLM_PROMPT_CHARS]
