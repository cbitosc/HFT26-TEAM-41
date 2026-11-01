"""Profiler rules (P2.1). The LLM is always a fake here; it is never called for real."""

import copy

import pytest
import yaml

from profiler import keywords
from profiler.profile import LLM_MAX_TOKENS, build_profile
from profiler.taxonomy import (
    TAXONOMY_PATH,
    concept_vocabulary,
    load_taxonomy,
    normalize_topic,
    parse_taxonomy,
)
from tests.api_support import fixture


class FakeLlm:
    """Stands in for llm.complete_structured; records each call."""

    def __init__(self, domain="web", runtime="node20", concepts=("auth",), fail=False):
        self.answer = {"domain": domain, "runtime": runtime, "concepts": list(concepts)}
        self.fail = fail
        self.calls: list[dict] = []

    def __call__(self, slot, messages, response_model, **kwargs):
        self.calls.append({"slot": slot, "messages": messages, **kwargs})
        if self.fail:
            raise RuntimeError("budget exceeded")
        return response_model(**self.answer)


def profile(name: str, llm: FakeLlm | None = None, **changes):
    doc = copy.deepcopy(fixture(f"portfolio.valid{name}.json"))
    doc.update(changes)
    return build_profile(doc, llm=llm or FakeLlm()).model_dump(mode="json")


def no_llm():
    return FakeLlm(fail=True)


# --- Fixtures, rules only ---


def test_python_backend() -> None:
    llm = FakeLlm()
    p = profile("", llm)

    assert llm.calls == []
    assert (p["domain"], p["runtime"], p["suggested_tier"]) == ("backend", "python311", "master")
    assert p["concepts"] == ["caching", "reporting", "validation"]
    assert p["sources"] == {"domain": "rules", "runtime": "rules", "concepts": "rules"}
    assert p["unsupported_notes"] == []
    assert p == fixture("profile.valid.json")  # the contract fixture is this real profile


def test_react_web() -> None:
    llm = FakeLlm()
    p = profile(".web", llm)

    assert llm.calls == []
    assert (p["domain"], p["runtime"]) == ("web", "node20")
    assert set(p["concepts"]) == {"pagination", "auth", "filtering", "reporting", "sorting"}
    assert p["concepts"][0] == "pagination"  # strongest evidence first
    assert p["suggested_tier"] == "novice"  # 26 solved < 40


def test_ml() -> None:
    p = profile(".ml", no_llm())

    assert (p["domain"], p["runtime"], p["suggested_tier"]) == ("ml", "python311", "adept")
    assert set(p["concepts"]) == {"validation", "caching", "reporting"}


def test_security() -> None:
    p = profile(".security", no_llm())

    assert (p["domain"], p["runtime"]) == ("security", "python311")
    assert "auth" in p["concepts"]
    assert p["allowed_topics"]["master"] == []


def test_messy_topic_names_map_to_canonical_topics() -> None:
    p = profile(".messy_topics", no_llm())

    assert p["topics_solved"] == {
        "dp": 4,  # dynamic_programming
        "graphs_bfs_dfs": 15,  # bfs 6 + dfs 9
        "hashing": 5,  # hash_map 3 + hashmap 2
        "linked_list": 1,
        "two_pointers": 5,
    }
    assert p["unsupported_notes"] == [
        "DSA topic 'recursion' is not in the taxonomy; ignored.",
        "DSA topic 'segment_tree' is not in the taxonomy; ignored.",
    ]


def test_unsupported_stack_maps_to_the_closest_runtime_with_a_note() -> None:
    llm = FakeLlm()
    p = profile(".go", llm)

    assert llm.calls == []
    assert (p["domain"], p["runtime"]) == ("backend", "python311")
    assert p["sources"]["runtime"] == "rules"
    assert p["unsupported_notes"] == [
        "Go is not a supported runtime; the domain task uses python311."
    ]


def test_unsupported_web_stack_maps_to_node() -> None:
    doc = fixture("portfolio.valid.web.json")
    for project in doc["projects"]:
        project["keywords"] = ["PHP", "Laravel", "Tailwind CSS"]
    doc["skills"] = [{"name": "Frontend", "keywords": ["PHP", "HTML", "CSS"]}]
    doc["basics"]["summary"] = "Frontend developer building responsive sites."

    p = build_profile(doc, llm=no_llm()).model_dump(mode="json")

    assert (p["domain"], p["runtime"]) == ("web", "node20")
    assert p["unsupported_notes"] == [
        "PHP is not a supported runtime; the domain task uses node20."
    ]


def test_go_in_prose_is_not_a_stack() -> None:
    doc = fixture("portfolio.valid.json")
    doc["basics"]["summary"] += " Happy to go the extra mile."

    assert build_profile(doc, llm=no_llm()).unsupported_notes == []


# --- LLM fallback ---


def test_vague_portfolio_calls_the_llm_once_with_limits() -> None:
    llm = FakeLlm(domain="web", runtime="node20", concepts=["auth", "caching"])
    p = profile(".vague", llm)

    [call] = llm.calls
    assert call["slot"] == "generator"
    assert (call["max_tokens"], call["temperature"]) == (LLM_MAX_TOKENS, 0)
    assert "pagination" in call["messages"][0]["content"]  # allowed values are listed
    assert (p["domain"], p["runtime"], p["concepts"]) == ("web", "node20", ["auth", "caching"])
    assert p["sources"] == {"domain": "llm", "runtime": "llm", "concepts": "llm"}


def test_an_llm_answer_outside_the_allowed_values_is_not_used() -> None:
    llm = FakeLlm(concepts=["blockchain"])  # the response model rejects it

    p = profile(".vague", llm)

    assert len(llm.calls) == 1
    assert p["concepts"] == [] and p["sources"]["concepts"] == "default"


def test_llm_fills_only_what_the_rules_left_empty() -> None:
    llm = FakeLlm(domain="ml", runtime="node20", concepts=["auth"])
    doc = fixture("portfolio.valid.go.json")
    doc["skills"] = [{"name": "Languages", "keywords": ["Go"]}]
    for project in doc["projects"]:
        project.update(description="Go service.", highlights=[], keywords=["Go"])

    p = build_profile(doc, llm=llm).model_dump(mode="json")

    assert len(llm.calls) == 1  # no concept found by the rules
    assert (p["domain"], p["runtime"]) == ("backend", "python311")  # rules win
    assert (p["concepts"], p["sources"]["concepts"]) == (["auth"], "llm")


def test_failed_llm_fallback_uses_defaults_and_says_so() -> None:
    p = profile(".vague", FakeLlm(fail=True))

    assert (p["domain"], p["runtime"], p["concepts"]) == ("backend", "python311", [])
    assert p["sources"] == {"domain": "default", "runtime": "default", "concepts": "default"}
    assert any("LLM fallback failed" in note for note in p["unsupported_notes"])


def test_the_llm_prompt_holds_no_contact_details_and_is_truncated() -> None:
    llm = FakeLlm()
    doc = fixture("portfolio.valid.vague.json")
    doc["basics"]["email"] = "sam@example.com"
    doc["basics"]["summary"] = "x " * 5000

    build_profile(doc, llm=llm)

    user = llm.calls[0]["messages"][1]["content"]
    assert "sam@example.com" not in user and "Sam Taylor" not in user
    assert len(user) <= 1500


# --- Thresholds and tiers ---


def solved(topics: dict[str, int], projects: int = 3):
    doc = fixture("portfolio.valid.json")
    doc["assessment"]["dsaTopicsSolved"] = topics
    doc["projects"] = doc["projects"][:1] * projects
    return build_profile(doc, llm=no_llm()).model_dump(mode="json")


def test_four_dp_is_easy_only() -> None:
    allowed = solved({"dp": 4})["allowed_topics"]

    assert (allowed["novice"], allowed["adept"], allowed["master"]) == (["dp"], [], [])


def test_five_dp_is_medium() -> None:
    assert solved({"dp": 5})["allowed_topics"]["adept"] == ["dp"]


def test_fifteen_dp_is_hard() -> None:
    allowed = solved({"dp": 15})["allowed_topics"]

    assert allowed["master"] == ["dp"]


def test_topics_follow_their_tiers() -> None:
    # shortest_paths is master-only in the taxonomy, however much it was solved.
    allowed = solved({"shortest_paths": 40})["allowed_topics"]

    assert (allowed["novice"], allowed["adept"], allowed["master"]) == ([], [], ["shortest_paths"])


@pytest.mark.parametrize(
    ("topics", "projects", "tier"),
    [
        ({"arrays": 150}, 3, "master"),
        ({"arrays": 149}, 3, "adept"),
        ({"arrays": 150}, 2, "adept"),  # too few projects for master
        ({"arrays": 40}, 2, "adept"),
        ({"arrays": 39}, 2, "novice"),
        ({"arrays": 40}, 1, "novice"),
        (
            {
                "arrays": 4,
                "dp": 4,
                "strings": 4,
                "hashing": 4,
                "greedy": 4,
                "bit_manipulation": 4,
                "two_pointers": 4,
                "stack": 4,
                "queue": 4,
                "sorting": 4,
            },
            2,
            "novice",
        ),  # fmt: skip
    ],
)
def test_suggested_tier(topics, projects, tier) -> None:
    p = solved(topics, projects)

    assert p["suggested_tier"] == tier
    assert p["tier_reason"]


def test_no_solved_topics_is_noted() -> None:
    p = solved({"arrays": 0})

    assert p["allowed_topics"] == {"novice": [], "adept": [], "master": []}
    assert (
        "No solved DSA topic from the taxonomy; no DSA topic is allowed."
        in (p["unsupported_notes"])
    )


# --- Taxonomy and vocabulary ---


def test_taxonomy_has_about_twenty_topics_with_thresholds() -> None:
    taxonomy = load_taxonomy()

    assert 20 <= len(taxonomy.topic_tiers) <= 25
    assert taxonomy.thresholds == {"easy": 1, "medium": 5, "hard": 15}
    for name in ["arrays", "hashing", "two_pointers", "sliding_window", "stack", "queue",
                 "linked_list", "binary_search", "trees", "bst", "heaps", "graphs_bfs_dfs",
                 "shortest_paths", "dp", "greedy", "backtracking", "tries", "union_find",
                 "bit_manipulation", "intervals"]:  # fmt: skip
        assert name in taxonomy.topic_tiers


def test_every_synonym_is_normalized_snake_case() -> None:
    raw = yaml.safe_load(TAXONOMY_PATH.read_text())
    for topic, entry in raw["topics"].items():
        for name in [topic, *entry["synonyms"]]:
            assert normalize_topic(name) == name


def test_a_synonym_claimed_by_two_topics_is_rejected() -> None:
    raw = yaml.safe_load(TAXONOMY_PATH.read_text())
    raw["topics"]["dp"]["synonyms"].append("bfs")

    with pytest.raises(ValueError, match="maps to both"):
        parse_taxonomy(raw)


def test_concept_vocabulary_is_the_union_of_seed_concepts() -> None:
    vocabulary = concept_vocabulary()

    assert "pagination" in vocabulary
    assert list(vocabulary) == sorted(set(vocabulary))
    # Every concept a seed teaches has keyword synonyms to be found by.
    assert set(vocabulary) <= set(keywords.CONCEPTS)
