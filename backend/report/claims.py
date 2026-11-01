"""Claim verification map: each portfolio claim vs what the assessment tested and how it went.

Claims come from the candidate's Profile (the stored one, else the rules-only profile of
the portfolio): the seed concepts the portfolio's keywords point to, the DSA topics it
reports problems for, and its runtime. A claim is tested by a task that exercises it (a
domain task's concept, a DSA task's tags, a task's runtime); its verdict comes from that
task's correctness. Report-only.
"""

from dataclasses import dataclass
from typing import Literal

from builder.tasks import load_seed
from contracts_gen.profile import Profile
from contracts_gen.task_spec import TaskSpec

VERIFIED_AT = 80.0
PARTLY_AT = 45.0
RUNTIME_NAMES = {"python311": "Python", "node20": "JavaScript (Node.js)"}

Verdict = Literal["verified", "partly", "not_verified", "not_tested"]


@dataclass(frozen=True)
class Claim:
    claim: str
    kind: Literal["concept", "dsa_topic", "runtime"]
    evidence: str
    tested_by: list[str]
    correctness: float | None
    """Mean correctness of the tasks that tested it."""
    verdict: Verdict


def verdict(correctness: float | None) -> Verdict:
    if correctness is None:
        return "not_tested"
    if correctness >= VERIFIED_AT:
        return "verified"
    return "partly" if correctness >= PARTLY_AT else "not_verified"


def concept_of(spec: TaskSpec) -> str | None:
    """The seed concept a domain task tests: named in its task id, else by its symbols."""
    if spec.kind != "domain" or not spec.seed_id:
        return None
    try:
        _, concepts = load_seed(spec.seed_id)
    except (FileNotFoundError, ValueError):
        return None
    names = list(concepts.get("concepts", {}))
    parts = spec.task_id.split("-")
    for name in names:
        if name in parts:
            return name
    targets = {s.split("::", 1)[1].rsplit(".", 1)[-1] for s in spec.target_symbols if "::" in s}
    for name in names:
        symbols = concepts["concepts"][name].get("symbols", [])
        if targets & {s.split("::", 1)[1].rsplit(".", 1)[-1] for s in symbols}:
            return name
    return None


def claim_map(
    profile: Profile, specs: list[TaskSpec], correctness: dict[str, float]
) -> list[Claim]:
    def result(task_ids: list[str]) -> tuple[float | None, Verdict]:
        scores = [correctness[t] for t in task_ids if t in correctness]
        mean = round(sum(scores) / len(scores), 2) if scores else None
        return mean, verdict(mean)

    concept_tasks: dict[str, list[str]] = {}
    for spec in specs:
        if (concept := concept_of(spec)) is not None:
            concept_tasks.setdefault(concept, []).append(spec.task_id)
    claims = []
    source = profile.sources.concepts
    for concept in (c.root for c in profile.concepts):
        tested = concept_tasks.get(concept, [])
        mean, label = result(tested)
        evidence = f"inferred from the portfolio ({source})"
        claims.append(Claim(concept.replace("_", " "), "concept", evidence, tested, mean, label))
    solved_by_topic = {topic: count.root for topic, count in profile.topics_solved.items()}
    for topic, solved in sorted(solved_by_topic.items(), key=lambda kv: (-kv[1], kv[0])):
        tested = [s.task_id for s in specs if s.kind == "dsa" and topic in s.dsa_tags]
        mean, label = result(tested)
        claims.append(
            Claim(
                topic.replace("_", " "),
                "dsa_topic",
                f"{solved} problems solved",
                tested,
                mean,
                label,
            )
        )
    tested = [s.task_id for s in specs if s.runtime == profile.runtime]
    mean, label = result(tested)
    runtime = RUNTIME_NAMES.get(profile.runtime, profile.runtime)
    claims.append(Claim(runtime, "runtime", "the portfolio's main language", tested, mean, label))
    return claims
