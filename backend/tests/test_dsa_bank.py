"""DSA bank (P2.6) without Docker: bank files, selection, stubs, rewriting (the LLM is
always a fake here) and the importer's parsing. Sandbox checks: test_dsa_bank_docker.py."""

import importlib.util
import itertools
import json
import random

import pytest

from builder import dsa_bank, dsa_rewrite
from builder.dsa_bank import NoProblemError, load_bank, select_problem
from builder.dsa_rewrite import DsaRewrite, RenamedParameter
from builder.seeds import DSA_DIR
from contracts_gen.profile import Profile
from contracts_gen.task_spec import TaskSpec
from profiler.taxonomy import TIERS, load_taxonomy

BANK = load_bank()
TOPICS = sorted(load_taxonomy().topic_tiers)


def profile(novice=(), adept=(), master=()) -> Profile:
    return Profile.model_validate(
        {
            "domain": "backend",
            "runtime": "python311",
            "concepts": [],
            "topics_solved": {},
            "allowed_topics": {
                "novice": list(novice),
                "adept": list(adept),
                "master": list(master),
            },
            "suggested_tier": "novice",
            "tier_reason": "test",
            "unsupported_notes": [],
            "sources": {"domain": "rules", "runtime": "rules", "concepts": "rules"},
        }
    )


def problem(problem_id: str) -> dsa_bank.BankProblem:
    return next(p for p in BANK if p.id == problem_id)


# --- Bank files ---


def test_bank_size_tiers_and_tags() -> None:
    taxonomy = load_taxonomy()
    assert 80 <= len(BANK) <= 121
    for tier in TIERS:
        assert sum(tier in p.tiers for p in BANK) >= 20, tier
    for p in BANK:
        assert set(p.tags) <= set(taxonomy.topic_tiers), p.id
        for tier in p.tiers:
            assert all(tier in taxonomy.topic_tiers[tag] for tag in p.tags), (p.id, tier)


def test_every_problem_has_its_files_and_enough_cases() -> None:
    for p in BANK:
        for name in ("problem.md", "stub.py", "reference.py", "cases.json"):
            assert (p.dir / name).is_file(), (p.id, name)
        cases = dsa_bank.load_cases(p)
        assert len(cases["visible"]) == 5, p.id
        assert len(cases["hidden"]) >= 10, p.id
        params = [param.name for param in p.signature.params]
        for case in cases["visible"] + cases["hidden"]:
            assert set(case) == {"id", "input", "expected"}
            assert list(case["input"]) == params, p.id


def test_the_p13_problem_is_in_the_bank() -> None:
    p = problem("longest_unique_substring")
    assert p.own_statement and p.tags == ["sliding_window"] and p.tiers == ["novice"]


def test_no_original_description_is_stored_outside_raw() -> None:
    raw = DSA_DIR / "raw" / "descriptions"
    if not raw.is_dir():
        pytest.skip("dsa/raw/ not present (run make dsa-import)")
    for p in BANK:
        original = raw / f"{p.id}.md"
        if not original.is_file():
            continue
        text = original.read_text()
        # problem.md's examples are case data; only its prose must not be copied.
        prose = (p.dir / "problem.md").read_text().split("## Your function")[0]
        for written in (prose, (p.dir / "problem.json").read_text()):
            assert dsa_rewrite.copied_words(written, text) is None, p.id


# --- Selection ---


def test_selection_never_returns_an_unclaimed_or_disallowed_tag() -> None:
    rng = random.Random(7)
    for seed in range(300):
        allowed = {tier: rng.sample(TOPICS, rng.randint(0, len(TOPICS))) for tier in TIERS}
        prof = profile(**allowed)
        tier = rng.choice(TIERS)
        try:
            chosen = select_problem(prof, tier, seed)
        except NoProblemError:
            continue
        assert chosen.tier in chosen.problem.tiers
        assert TIERS.index(chosen.tier) <= TIERS.index(tier)
        assert set(chosen.problem.tags) <= set(allowed[chosen.tier]), chosen.reason


def test_selection_is_deterministic_per_seed_and_varies_across_seeds() -> None:
    prof = profile(novice=TOPICS)
    picks = {select_problem(prof, "novice", seed).problem.id for seed in range(20)}
    assert len(picks) > 1
    assert select_problem(prof, "novice", 3) == select_problem(prof, "novice", 3)


def test_fallback_to_the_easiest_lower_tier_problem_records_why() -> None:
    prof = profile(novice=["sliding_window"], adept=[])
    chosen = select_problem(prof, "adept", 1)
    assert chosen.tier == "novice"
    assert chosen.problem.id == "longest_unique_substring"
    assert "no adept problem" in chosen.reason and "fell back" in chosen.reason


def test_no_problem_at_all_raises_with_the_reason() -> None:
    with pytest.raises(NoProblemError, match="none fits a lower tier"):
        select_problem(profile(), "master", 1)


# --- Practice-only split ---


def test_about_a_third_of_each_difficulty_is_practice_only() -> None:
    practice = dsa_bank.practice_split(BANK)
    assert dsa_bank.PRACTICE_PINNED <= practice
    for difficulty in dsa_bank.DIFFICULTY_RANK:
        group = [p for p in BANK if p.difficulty == difficulty]
        assert sum(p.id in practice for p in group) == round(len(group) / 3), difficulty
    assert not any(p.own_statement for p in BANK if p.id in practice)
    assert dsa_bank.practice_split(BANK) == practice  # deterministic


def test_committed_flags_match_the_split() -> None:
    assert {p.id for p in BANK if p.practice_only} == dsa_bank.practice_split(BANK)


def test_every_profile_that_fit_a_problem_still_gets_an_assessment_problem() -> None:
    assert dsa_bank.assessment_covers(BANK, {p.id for p in BANK if p.practice_only})
    for tier in TIERS:
        assert sum(tier in p.tiers and not p.practice_only for p in BANK) >= 20, tier


def test_selection_never_picks_a_practice_only_problem() -> None:
    rng = random.Random(11)
    picked = 0
    for seed in range(400):
        allowed = {tier: rng.sample(TOPICS, rng.randint(1, len(TOPICS))) for tier in TIERS}
        try:
            chosen = select_problem(profile(**allowed), rng.choice(TIERS), seed)
        except NoProblemError:
            continue
        picked += 1
        assert not chosen.problem.practice_only, chosen.problem.id
    assert picked > 100
    # A profile whose only fitting problem is practice-only falls through to the next rule.
    only_two_sum = profile(novice=problem("two_sum").tags)
    assert select_problem(only_two_sum, "novice", 0).problem.id != "two_sum"


# --- Stubs and statements ---


def test_stubs_and_statement_use_the_renamed_names() -> None:
    p = problem("two_sum")
    names = names_for(p, "find_pair", {"nums": "amounts", "target": "goal"})
    js = dsa_bank.js_stub(p, names)
    assert "function find_pair(amounts, goal)" in js
    assert "module.exports = { find_pair };" in js
    assert "@param {number[]} amounts" in js and "@returns {number[]}" in js
    py = dsa_bank.python_stub(p, names)
    assert py.startswith("def find_pair(amounts: list[int], goal: int) -> list[int]:")
    visible = dsa_bank.load_cases(p)["visible"]
    renamed = [c | {"input": dsa_bank.rename_input(c["input"], names)} for c in visible]
    text = dsa_bank.statement_md(p, "A story.", names, "node20", renamed)
    assert text.count("**Example") == 2 and "find_pair(amounts = " in text
    assert "any order" in text


def test_python_literals_in_examples() -> None:
    assert dsa_bank.literal([True, None, "a"], "python311") == '[True, None, "a"]'
    assert dsa_bank.literal([True, None, "a"], "node20") == '[true, null, "a"]'


def test_task_spec_renames_case_inputs_and_keeps_ids() -> None:
    p = problem("two_sum")
    names = names_for(p, "find_pair", {"nums": "amounts", "target": "goal"})
    spec = TaskSpec.model_validate(dsa_bank.task_spec(p, "Story.", names, "node20", "novice"))
    assert spec.seed_id == "two_sum" and spec.dsa_names == names
    assert spec.entry_symbols == ["solution.js::find_pair"]
    assert all(set(c.input) == {"amounts", "goal"} for c in spec.dsa_cases.hidden)
    assert spec.hidden_test_ids == [c.id for c in spec.dsa_cases.hidden]
    assert spec.dsa_cases.comparator.kind == "unordered_list"


def test_wrapped_reference_calls_the_original_with_the_new_names() -> None:
    p = problem("two_sum")
    names = names_for(p, "two_sum", {"nums": "amounts", "target": "goal"})
    source = dsa_bank.wrapped_reference(p, names)
    assert source.endswith(
        "_bank_reference = two_sum\n\n\ndef two_sum(amounts, goal):\n"
        "    return _bank_reference(nums=amounts, target=goal)\n"
    )


def names_for(p, function: str, params: dict[str, str]):
    reply = DsaRewrite(
        statement="x",
        function_name=function,
        parameters=[RenamedParameter(original=k, renamed=v) for k, v in params.items()],
    )
    return dsa_rewrite.validate_reply(p, reply, "")


# --- Rewriting ---


class FakeLlm:
    """Stands in for llm.complete_structured; returns the queued replies in order."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def __call__(self, slot, messages, response_model, temperature, max_tokens):
        self.calls.append(
            {
                "slot": slot,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def reply(function="find_pair", **params) -> DsaRewrite:
    params = params or {"nums": "amounts", "target": "goal"}
    return DsaRewrite(
        statement="An expenses API keeps amounts; find two that add up to the goal.",
        function_name=function,
        parameters=[RenamedParameter(original=k, renamed=v) for k, v in params.items()],
    )


@pytest.fixture
def described(monkeypatch):
    """two_sum with a cached original description, wherever dsa/raw/ is."""
    monkeypatch.setattr(dsa_rewrite, "load_description", lambda p: "Find two numbers. " * 3)
    return problem("two_sum")


def rewrite(p, llm, check=lambda names: None):
    return dsa_rewrite.rewrite_problem(p, "backend", ["expense-tracker"], check=check, llm=llm)


def test_a_good_rewrite_maps_names_one_to_one(described) -> None:
    llm = FakeLlm(reply())
    result = rewrite(described, llm)
    assert result.source == "llm" and result.notes == []
    mapping = {m.original: m.renamed for m in result.names.parameters}
    assert mapping == {"nums": "amounts", "target": "goal"}
    assert len(set(mapping.values())) == len(mapping)
    assert result.names.function.renamed == "find_pair"
    (call,) = llm.calls
    assert call["slot"] == "generator" and call["max_tokens"] == 600
    assert call["temperature"] == 0.2
    assert "expense-tracker" in call["messages"][1]["content"]


@pytest.mark.parametrize(
    "bad",
    [
        reply(nums="amounts", target="amounts"),  # two parameters, one name
        reply(nums="amounts"),  # a parameter left out
        reply(nums="amounts", target="goal", extra="x"),  # an unknown parameter
        reply(function="class"),  # reserved in JS and Python
        reply(function="find-pair"),  # not an identifier
        reply(nums="sum", target="goal"),  # a Python built-in
        reply(function="goal"),  # function and parameter share a name
    ],
)
def test_a_broken_mapping_retries_once_then_uses_the_template(described, bad) -> None:
    llm = FakeLlm(bad, bad)
    result = rewrite(described, llm)
    assert result.source == "template"
    assert result.names == dsa_bank.identity_names(described)
    assert len(llm.calls) == 2
    assert len(result.notes) == 3 and "template" in result.notes[-1]
    # The retry is a different conversation, so it can't come back from the cache.
    assert llm.calls[0]["messages"] != llm.calls[1]["messages"]


def test_the_retry_can_fix_it(described) -> None:
    llm = FakeLlm(reply(function="class"), reply())
    result = rewrite(described, llm)
    assert result.source == "llm" and len(result.notes) == 1


def test_a_reference_mismatch_rejects_the_rewrite(described) -> None:
    llm = FakeLlm(reply(), reply())
    result = rewrite(described, llm, check=lambda names: "the renamed reference passed 0/5")
    assert result.source == "template"
    assert "0/5" in result.notes[0]


def test_a_copied_statement_is_rejected(described, monkeypatch) -> None:
    original = "given an array of integers nums and an integer target return indices of two"
    monkeypatch.setattr(dsa_rewrite, "load_description", lambda p: original)
    copied = reply().model_copy(update={"statement": f"In our API, {original}."})
    result = rewrite(described, FakeLlm(copied, copied))
    assert result.source == "template" and "copies the original" in result.notes[0]


def test_a_statement_using_an_old_parameter_name_is_rejected(described) -> None:
    stale = reply().model_copy(update={"statement": "Sum the `nums` to reach the goal."})
    result = rewrite(described, FakeLlm(stale, reply()))
    assert result.source == "llm" and "old names ['nums']" in result.notes[0]


def test_an_llm_failure_falls_back_without_a_retry(described) -> None:
    llm = FakeLlm(RuntimeError("budget reached"))
    result = rewrite(described, llm)
    assert result.source == "template" and len(llm.calls) == 1


def test_missing_raw_uses_the_template_and_logs_it(monkeypatch) -> None:
    p = problem("two_sum")
    monkeypatch.setattr(dsa_rewrite, "load_description", lambda p: None)
    llm = FakeLlm()
    result = rewrite(p, llm)
    assert result.source == "template" and llm.calls == []
    assert "dsa/raw/ missing" in result.notes[0]
    assert "two_sum" in result.story.lower().replace(" ", "_")


def test_the_prompt_drops_the_examples_and_keeps_constraints() -> None:
    text = "Rules here.\n\nExample 1:\nInput: x = 1\n\nConstraints:\n1 <= x <= 5\n"
    trimmed = dsa_rewrite.trim_description(text)
    assert "Example" not in trimmed and "Rules here." in trimmed and "1 <= x" in trimmed


def test_build_uses_the_template_names_end_to_end_with_a_fake_grader(described) -> None:
    class Grade:
        def __init__(self, spec, files):
            full = bool(files)
            self.visible_passed = set(spec.visible_test_ids) if full else set()
            self.hidden_passed = set(spec.hidden_test_ids) if full else set()

    built = dsa_bank.build_dsa_task(
        described, "node20", "novice", "backend", ["expense-tracker"], FakeLlm(reply()), Grade
    )
    spec = TaskSpec.model_validate(built.spec)
    assert spec.runtime == "node20" and spec.starter_files.keys() == {"solution.js"}
    assert built.validation["statement"] == "llm"
    assert spec.certificate.reference_pass and spec.certificate.starter_fail
    assert "find_pair" in spec.statement_md


# --- Importer parsing (no exec, no eval) ---


def importer():
    path = DSA_DIR / "tools" / "import_leetcode.py"
    spec = importlib.util.spec_from_file_location("import_leetcode", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_importer_parses_inputs_as_keyword_literals_only() -> None:
    imp = importer()
    assert imp.parse_input("nums = [1,2], k = -3", ["nums", "k"]) == {"nums": [1, 2], "k": -3}
    for bad in ("__import__('os').system('x')", "nums = [1], k = f(2)", "[1, 2]", "nums = {1}"):
        with pytest.raises((imp.Skip, ValueError, SyntaxError)):
            imp.parse_input(bad, ["nums", "k"])
    with pytest.raises(imp.Skip):
        imp.parse_input("nums = [1]", ["nums", "k"])
    with pytest.raises(imp.Skip):
        imp.to_json(2**60)


def test_importer_keeps_only_json_signatures() -> None:
    imp = importer()
    method, params, returns = imp.signature(
        "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n"
    )
    assert (method, params, returns) == (
        "twoSum",
        [("nums", "list[int]"), ("target", "int")],
        "list[int]",
    )
    with pytest.raises(imp.Skip):
        imp.signature("class Solution:\n    def f(self, head: Optional[ListNode]) -> int:\n")
    assert imp.snake("lengthOfLongestSubstring") == "length_of_longest_substring"


def test_case_json_matches_the_signature_types() -> None:
    imp = importer()
    for p in itertools.islice(BANK, 0, None, 10):
        types = {param.name: param.type for param in p.signature.params}
        for case in dsa_bank.load_cases(p)["hidden"]:
            assert all(imp.conforms(case["input"][k], t) for k, t in types.items()), p.id
            assert imp.conforms(case["expected"], p.signature.returns), p.id


def test_problem_json_is_committed_without_descriptions() -> None:
    for p in BANK:
        data = json.loads((p.dir / "problem.json").read_text())
        assert "problem_description" not in data and "description" not in data
