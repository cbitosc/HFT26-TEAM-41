"""Validation gate (P2.7) without Docker: a fake grader stands in for the sandbox.

Each check passes on a good task and fails on a purpose-built bad one.
"""

import copy
from typing import Any

import pytest

from app.grading import TaskGrade
from builder.dsa_bank import task_spec as bank_task_spec
from builder.enrich import rename_source, renamed_spec
from builder.manual import PAGINATION_STATEMENT, dsa_task_spec, inject_offset_bug
from builder.seeds import SEEDS_DIR, seed_files
from builder.tasks import draft_certificate, starter_base
from contracts_gen.run_result import RunResult, Summary
from contracts_gen.run_result import TestResult as Result
from contracts_gen.task_spec import DsaNames, NameMapping, TaskSpec
from gate import certify, check, leak, validate
from gate.diff import diff
from gate.stubs import empty_value, stub_fail_rates
from scoring.score_session import _mutation_score
from tests.test_dsa_bank import problem, profile

SEED = "py-fastapi-expenses"
FILES = seed_files(SEEDS_DIR / SEED)
VISIBLE = [
    "tests/test_pagination.py::test_last_page_is_partial_and_has_no_next",
    "tests/test_pagination.py::test_first_page_reports_total_and_has_next",
]
HIDDEN = [
    "tests/test_pagination_hidden.py::test_pages_do_not_overlap",
    "tests/test_filtering.py::test_filter_by_category",
]
OTHER_CONCEPT = "tests/test_filtering.py::test_filter_by_category"
PROFILE = profile(novice=["sliding_window"])


def domain_spec(tier: str = "novice", **changes: Any) -> dict[str, Any]:
    starter = starter_base(FILES)
    starter["app/utils.py"] = inject_offset_bug(FILES["app/utils.py"])
    spec = {
        "task_id": "gate-pagination",
        "version": 1,
        "tier": tier,
        "kind": "domain",
        "mode": "seed",
        "seed_id": SEED,
        "runtime": "python311",
        "dsa_tags": [],
        "statement_md": PAGINATION_STATEMENT,
        "repo_tour_md": "",
        "starter_files": starter,
        "reference_ref": f"seeds/{SEED}",
        "target_symbols": ["app/utils.py::paginate"],
        "entry_symbols": ["app/routes.py::list_expenses"],
        "visible_tests": [{"path": "tests/test_pagination.py", "content": "# visible\n"}],
        "hidden_tests": [{"path": "tests/test_pagination_hidden.py", "content": "# hidden\n"}],
        "visible_test_ids": VISIBLE,
        "hidden_test_ids": HIDDEN,
        "dsa_cases": None,
        "perf": None,
        "time_budget_min": 35,
        "random_seeds": [],
        "certificate": draft_certificate(["app/utils.py"]),
        "ai_solve_rate": 0.0,
        "difficulty_index": 0.0,
    }
    return spec | changes


def _run(ids: list[str], failing: set[str]) -> RunResult:
    tests = [
        Result(
            id=i,
            name=i,
            outcome="failed" if i in failing else "passed",
            duration_ms=1,
            message=None,
        )
        for i in ids
    ]
    passed = sum(t.outcome == "passed" for t in tests)
    return RunResult(
        status="ok",
        reason=None,
        duration_ms=1,
        tests=tests,
        summary=Summary(passed=passed, failed=len(tests) - passed, total=len(tests)),
        stdout_tail="",
        stderr_tail="",
    )


class FakeGrade:
    """The reference (any candidate files) passes everything unless told otherwise; the
    starter (no candidate files) fails `starter_fails`. `flaky`: the 2nd reference run differs."""

    def __init__(
        self,
        starter_fails: set[str] | None = None,
        reference_fails: frozenset[str] = frozenset(),
        flaky: bool = False,
    ) -> None:
        self.starter_fails = {VISIBLE[0], HIDDEN[0]} if starter_fails is None else starter_fails
        self.reference_fails = reference_fails
        self.flaky = flaky
        self.reference_runs = 0
        self.graded_files: list[dict[str, str]] = []

    def __call__(self, spec: TaskSpec, files: dict[str, str]) -> TaskGrade:
        self.graded_files.append(files)
        failing = set(self.reference_fails) if files else set(self.starter_fails)
        if files:
            self.reference_runs += 1
            if self.flaky and self.reference_runs == 2:
                failing = {spec.visible_test_ids[0]}
        visible = _run(spec.visible_test_ids, failing)
        hidden = _run(spec.hidden_test_ids, failing)
        return TaskGrade(
            visible=visible,
            hidden=hidden,
            visible_passed={t.id for t in visible.tests if t.outcome == "passed"},
            hidden_passed={t.id for t in hidden.tests if t.outcome == "passed"},
            integrity={},
        )


def same_ids(spec: dict[str, Any]) -> dict[str, Any]:
    return spec


def run_gate(spec, grade=None, gate_profile=PROFILE, **options):
    return validate(spec, gate_profile, grade=grade or FakeGrade(), derive=same_ids, **options)


def codes(reasons: list[dict[str, Any]]) -> list[str]:
    return [r["code"] for r in reasons]


# --- Domain ---------------------------------------------------------------------------


def test_a_good_novice_task_gets_a_certificate() -> None:
    certificate, reasons = run_gate(domain_spec())

    assert reasons == []
    assert certificate.model_dump(mode="json") == {
        "reference_pass": "4/4 x3",
        "starter_fail": "1/2 visible",
        "mutation_score": None,  # not measured: mutation testing is off by default
        "stub_fail_rate": None,
        "bruteforce_agree": None,
        "budget_ms": None,
        "changed_lines": 1,
        "perf_ref_ms": None,
        "perf_naive_ms": None,
        "scope_files": ["app/utils.py"],
    }


def test_certify_records_fail_to_pass_and_pass_to_pass() -> None:
    spec, reasons = certify(domain_spec(), PROFILE, grade=FakeGrade(), derive=same_ids)

    assert reasons == []
    assert spec["fail_to_pass"] == {"visible": [VISIBLE[0]], "hidden": [HIDDEN[0]]}
    assert spec["pass_to_pass"] == {"visible": [VISIBLE[1]], "hidden": [HIDDEN[1]]}
    assert spec["certificate"]["reference_pass"] == "4/4 x3"
    TaskSpec.model_validate(spec)


def test_the_reference_runs_three_times_with_the_seed_files() -> None:
    grade = FakeGrade()
    run_gate(domain_spec(), grade)

    assert grade.reference_runs == 3
    assert grade.graded_files[0]["app/utils.py"] == FILES["app/utils.py"]


def test_a_flaky_reference_is_rejected() -> None:
    certificate, reasons = run_gate(domain_spec(), FakeGrade(flaky=True))

    assert certificate is None
    assert codes(reasons) == ["reference_flaky"]
    assert reasons[0]["items"] == [VISIBLE[0]]


def test_a_failing_reference_is_rejected() -> None:
    _, reasons = run_gate(domain_spec(), FakeGrade(reference_fails=frozenset({HIDDEN[1]})))

    assert codes(reasons) == ["reference_fails"]
    assert reasons[0]["items"] == [HIDDEN[1]]


def test_a_starter_that_passes_the_visible_tests_is_rejected() -> None:
    _, reasons = run_gate(domain_spec(), FakeGrade(starter_fails={HIDDEN[0]}))

    assert codes(reasons) == ["starter_passes"]


def test_novice_and_adept_starters_must_fail_a_hidden_test_too() -> None:
    _, reasons = run_gate(domain_spec(), FakeGrade(starter_fails={VISIBLE[0]}))

    assert codes(reasons) == ["starter_passes_hidden"]


def test_a_novice_starter_must_pass_every_test_outside_the_target_concept() -> None:
    _, reasons = run_gate(domain_spec(), FakeGrade(starter_fails={VISIBLE[0], OTHER_CONCEPT}))

    assert codes(reasons) == ["starter_breaks_other_concepts"]
    assert reasons[0]["items"] == [OTHER_CONCEPT]


def test_hidden_copies_of_concept_tests_count_as_the_concept() -> None:
    hidden_pagination = "tests/test_pagination_hidden.py::test_pages_do_not_overlap[2]"
    spec = domain_spec(hidden_test_ids=[hidden_pagination, OTHER_CONCEPT])
    _, reasons = run_gate(spec, FakeGrade(starter_fails={VISIBLE[0], hidden_pagination}))

    assert reasons == []


def test_a_novice_fix_in_two_files_is_out_of_scope() -> None:
    spec = domain_spec()
    spec["starter_files"]["app/services.py"] += "\nSTRAY_CHANGE = 1\n"
    _, reasons = run_gate(spec)

    assert codes(reasons) == ["scope_files"]
    assert reasons[0]["items"] == ["app/services.py", "app/utils.py"]


def test_a_novice_fix_over_ten_lines_is_out_of_scope() -> None:
    spec = domain_spec()
    spec["starter_files"]["app/utils.py"] += "".join(f"EXTRA_{i} = {i}\n" for i in range(10))
    _, reasons = run_gate(spec)

    assert codes(reasons) == ["scope_lines"]
    assert "11 lines" in reasons[0]["detail"]


def test_adept_needs_two_or_three_files() -> None:
    _, one_file = run_gate(domain_spec("adept"))
    spec = domain_spec("adept")
    spec["starter_files"]["app/services.py"] += "\nREMOVED_FEATURE = None\n"
    _, two_files = run_gate(spec)

    assert codes(one_file) == ["scope_files"]
    assert two_files == []


PERF_TEST = {"path": "tests/perf/test_report_perf.py", "content": "# timed\n"}


def master_spec(perf: dict[str, Any] | None, ref_ms=40.0, naive_ms=900.0) -> dict[str, Any]:
    spec = domain_spec("master", perf=perf)
    spec["hidden_tests"] = spec["hidden_tests"] + [PERF_TEST]
    spec["starter_files"]["app/services.py"] += "\nNAIVE_LOOKUP = True\n"
    spec["certificate"] |= {"perf_ref_ms": ref_ms, "perf_naive_ms": naive_ms}
    return spec


PERF = {"budget_ms": 120, "input_gen": "many_expenses"}


def test_master_with_perf_calibration_passes_and_records_it() -> None:
    certificate, reasons = run_gate(master_spec(PERF))

    assert reasons == []
    assert (certificate.perf_ref_ms, certificate.perf_naive_ms, certificate.budget_ms) == (
        40.0,
        900.0,
        120,
    )


def test_master_without_perf_is_rejected() -> None:
    _, reasons = run_gate(master_spec(None))

    assert codes(reasons) == ["perf_missing"]


@pytest.mark.parametrize(
    ("ref_ms", "naive_ms", "code"),
    [
        (None, 900.0, "perf_uncalibrated"),
        (200.0, 900.0, "perf_reference_over_budget"),
        (40.0, 100.0, "perf_starter_within_budget"),
    ],
)
def test_master_perf_calibration_must_hold(ref_ms, naive_ms, code) -> None:
    _, reasons = run_gate(master_spec(PERF, ref_ms, naive_ms))

    assert codes(reasons) == [code]


def test_a_perf_budget_without_a_hidden_perf_test_is_rejected() -> None:
    spec = master_spec(PERF)
    spec["hidden_tests"] = [t for t in spec["hidden_tests"] if t != PERF_TEST]
    _, reasons = run_gate(spec)

    assert codes(reasons) == ["perf_test_missing"]


def test_comment_and_whitespace_changes_are_not_part_of_the_scope() -> None:
    spec = domain_spec()
    utils = spec["starter_files"]["app/utils.py"]
    spec["starter_files"]["app/utils.py"] = "# reworded header comment\n\n\n" + utils.replace(
        "offset = (page - 2) * page_size", "offset = (page-2)*page_size  # hmm"
    )
    spec["starter_files"]["app/services.py"] += "\n\n# only a comment here\n   \n"
    certificate, reasons = run_gate(spec)

    assert reasons == []
    assert certificate.model_dump(mode="json")["scope_files"] == ["app/utils.py"]
    assert certificate.changed_lines == 1


def test_scope_counts_code_lines_once_per_replaced_line() -> None:
    changes = diff(
        {"a.py": "x = 1\ny = 2\n", "b.py": "z = 0\n"},
        {"a.py": "x = 2\ny = 3\nw = 4\n", "b.py": "z = 0  # same code\n"},
    )

    assert (changes.files, changes.changed_lines) == (["a.py"], 3)
    assert changes.reference_lines == ["x = 2", "y = 3", "w = 4"]


def test_test_ids_must_match_the_derived_ones() -> None:
    def derive(spec):
        return spec | {"hidden_test_ids": HIDDEN[:1]}

    certificate, reasons = validate(domain_spec(), PROFILE, grade=FakeGrade(), derive=derive)

    assert certificate is None
    assert codes(reasons) == ["test_ids_mismatch"]
    assert reasons[0]["items"] == [HIDDEN[1]]


def test_test_ids_that_cannot_be_derived_reject_the_task() -> None:
    def derive(spec):
        raise ValueError("hidden tests of gate-pagination could not run: error")

    _, reasons = validate(domain_spec(), PROFILE, grade=FakeGrade(), derive=derive)

    assert codes(reasons) == ["test_ids_underivable"]


@pytest.mark.parametrize(
    "statement",
    [
        PAGINATION_STATEMENT + "\nHint: it should be `offset = (page - 1) * page_size`.\n",
        PAGINATION_STATEMENT + "\nThe offset must use `page - 1`.\n",
        PAGINATION_STATEMENT + "\nRemember: (page-1) times the page size.\n",
    ],
)
def test_a_statement_that_gives_the_fix_away_is_rejected(statement) -> None:
    _, reasons = run_gate(domain_spec(statement_md=statement))

    assert codes(reasons) == ["statement_leak"]


def test_an_unknown_reference_is_rejected() -> None:
    _, reasons = run_gate(domain_spec(reference_ref="seeds/no-such-seed"))

    assert codes(reasons) == ["reference_missing"]


def test_a_renamed_task_is_checked_against_the_renamed_reference() -> None:
    spec = renamed_spec(domain_spec(), {"expense": "order"})
    spec |= {"visible_test_ids": VISIBLE, "hidden_test_ids": HIDDEN}
    grade = FakeGrade()
    certificate, reasons = run_gate(spec, grade)

    assert reasons == [] and certificate.changed_lines == 1
    utils = grade.graded_files[0]["app/utils.py"]
    assert utils == rename_source("app/utils.py", FILES["app/utils.py"], {"expense": "order"})


def test_mutation_score_is_filled_only_when_asked() -> None:
    def fake_mutmut(spec, reference, scope_files):
        assert scope_files == ["app/utils.py"]
        return 0.85

    off, _ = run_gate(domain_spec(), mutation_score=fake_mutmut)
    on, _ = run_gate(domain_spec(), mutation=True, mutation_score=fake_mutmut)

    assert (off.mutation_score, on.mutation_score) == (None, 0.85)


# --- Leak checks (gate/leak.py) -------------------------------------------------------


def test_leak_checks_ignore_prose_and_short_lines() -> None:
    starter = {"a.py": "def f(xs):\n    return xs\n"}
    reference = {"a.py": "def f(xs):\n    return total\n"}

    assert leak.domain_leaks("It should return total spend.", starter, reference) == []


def test_a_multi_token_fix_leaks_without_its_context() -> None:
    starter = {"u.py": "offset = page * page_size\n"}
    reference = {"u.py": "offset = (page - 1) * page_size\n"}

    assert "contains the fix `( page - 1 )`" in leak.domain_leaks(
        "Use `(page - 1)` for it.", starter, reference
    )


@pytest.mark.parametrize(
    "statement",
    [
        "Set label = 'total' first.",  # other quote style
        "Set label = \u201ctotal\u201d first.",  # smart quotes
        'Set `label` = `"total"` first.',  # backticks inside the snippet
    ],
)
def test_leak_check_ignores_quote_style_and_backticks(statement) -> None:
    starter, reference = {"m.py": 'label = "sum"\n'}, {"m.py": 'label = "total"\n'}

    assert leak.domain_leaks(statement, starter, reference)


def test_leak_lines_ignore_the_reference_comment() -> None:
    starter = {"m.py": "offset = page * size\n"}
    reference = {"m.py": "offset = (page - 1) * size  # first page is 1\n"}

    assert "contains reference line `offset = (page - 1) * size`" in leak.domain_leaks(
        "Use offset = (page - 1) * size.", starter, reference
    )


def test_fix_fragments_cover_an_operator_flip() -> None:
    fragments = leak.fix_fragments("return a < b", "return a <= b")

    assert ["a", "<=", "b"] in fragments
    starter, reference = {"m.py": "return a < b\n"}, {"m.py": "return a <= b\n"}
    assert leak.domain_leaks("make it `a <= b`", starter, reference) == [
        "contains the fix `a <= b`"
    ]


def test_each_edit_of_a_split_fix_is_a_fragment() -> None:
    # Two separate edits: `<` -> `<=` and `0` -> `1`. Each one alone gives the fix away.
    fragments = leak.fix_fragments("if a < limit and b > 0:", "if a <= limit and b > 1:")

    assert ["a", "<=", "limit"] in fragments
    assert [">", "1", ":"] in fragments
    assert ["1"] not in fragments  # a lone 1 is too short to count on its own
    starter = {"m.py": "if a < limit and b > 0:\n"}
    reference = {"m.py": "if a <= limit and b > 1:\n"}
    assert leak.domain_leaks("check that b > 1: holds", starter, reference)


def test_a_split_fix_span_counts_with_one_token_of_context() -> None:
    fragments = leak.fix_fragments("x = f(a, 0)", "x = g(a, 1)")

    assert ["=", "g", "(", "a", ",", "1", ")"] in fragments


def test_statement_problems_add_the_word_limit_to_leaks() -> None:
    lines, fragments = leak.fix_evidence({"m.py": "return a <= b\n"}, {"m.py": "return a < b\n"})

    assert leak.statement_problems("make it `a <= b`", lines, fragments) == [
        "contains the fix `a <= b`"
    ]
    assert leak.statement_problems("word " * 201, lines, fragments) == ["longer than 200 words"]
    assert not leak.too_long("word " * 200)


def test_name_leaks_check_only_renamed_names_of_three_or_more_chars() -> None:
    names = DsaNames(
        function=NameMapping(original="two_sum", renamed="find_pair"),
        parameters=[
            NameMapping(original="nums", renamed="amounts"),
            NameMapping(original="k", renamed="goal"),
            NameMapping(original="target", renamed="target"),
        ],
    )

    assert leak.name_leaks("Given nums and k, find a target pair.", names) == ["nums"]
    assert leak.name_leaks("Use two_sum_cache here", names) == []
    assert leak.name_leaks("anything", None) == []


# --- DSA ------------------------------------------------------------------------------


def test_a_good_dsa_task_gets_a_certificate_with_its_stub_fail_rate() -> None:
    spec = dsa_task_spec()
    certificate, reasons = run_gate(
        spec, FakeGrade(starter_fails=set(spec["visible_test_ids"]) | set(spec["hidden_test_ids"]))
    )

    assert reasons == []
    total = len(spec["visible_test_ids"]) + len(spec["hidden_test_ids"])
    assert certificate.reference_pass.root == f"{total}/{total} x3"
    assert certificate.model_dump(mode="json")["scope_files"] == ["solution.py"]
    assert certificate.changed_lines is None
    assert certificate.stub_fail_rate == pytest.approx(
        min(stub_fail_rates(TaskSpec.model_validate(spec)).values()), abs=1e-4
    )
    assert certificate.stub_fail_rate >= 0.9


def dsa_grade(spec: dict[str, Any]) -> FakeGrade:
    return FakeGrade(starter_fails=set(spec["visible_test_ids"]) | set(spec["hidden_test_ids"]))


def test_a_dsa_tag_outside_the_profiles_allowed_topics_is_rejected() -> None:
    spec = dsa_task_spec()
    _, reasons = run_gate(spec, dsa_grade(spec), gate_profile=profile(adept=["sliding_window"]))

    assert codes(reasons) == ["tag_not_allowed"]
    assert reasons[0]["items"] == ["sliding_window"]


def test_weak_dsa_tests_are_rejected() -> None:
    spec = copy.deepcopy(dsa_task_spec())
    for case in spec["dsa_cases"]["visible"][1:] + spec["dsa_cases"]["hidden"]:
        case["expected"] = 0  # the `return 0` stub now gets almost every case right
    _, reasons = run_gate(spec, dsa_grade(spec))

    assert codes(reasons) == ["weak_tests"]
    assert any(item.startswith("zero fails") for item in reasons[0]["items"])
    assert any(item.startswith("empty_value fails") for item in reasons[0]["items"])


def test_stub_fail_rates_cover_identity_and_empty_stubs() -> None:
    spec = copy.deepcopy(dsa_task_spec()) | {"seed_id": "not_in_bank"}  # str returns
    cases = spec["dsa_cases"]
    cases["comparator"] = None
    cases["visible"] = [{"id": "v1", "input": {"s": "ab"}, "expected": "ab"}]
    cases["hidden"] = [{"id": "h1", "input": {"s": ""}, "expected": ""}]
    rates = stub_fail_rates(
        TaskSpec.model_validate(spec | {"visible_test_ids": ["v1"], "hidden_test_ids": ["h1"]})
    )

    assert rates == {"first_argument": 0.0, "empty_value": 0.5, "zero": 1.0, "none": 1.0}


def test_the_empty_stub_uses_the_declared_return_type() -> None:
    spec = TaskSpec.model_validate(renamed_dsa_spec("Find two expenses."))

    assert empty_value(spec) == []  # two_sum returns list[int]


def test_without_a_bank_signature_the_empty_stub_uses_the_common_expected_type() -> None:
    spec = copy.deepcopy(dsa_task_spec()) | {"seed_id": "not_in_bank"}
    spec["dsa_cases"]["visible"][0]["expected"] = None
    for case in spec["dsa_cases"]["visible"][1:] + spec["dsa_cases"]["hidden"]:
        case["expected"] = "abc"

    assert empty_value(TaskSpec.model_validate(spec)) == ""


def test_the_first_argument_stub_follows_the_parameter_order() -> None:
    spec = renamed_dsa_spec("Find two expenses.")
    for case in spec["dsa_cases"]["visible"] + spec["dsa_cases"]["hidden"]:
        case["input"] = {"goal": case["input"]["goal"], "amounts": case["input"]["amounts"]}
        case["expected"] = case["input"]["amounts"]  # identity on the first parameter

    assert stub_fail_rates(TaskSpec.model_validate(spec))["first_argument"] == 0.0


def renamed_dsa_spec(story: str) -> dict[str, Any]:
    p = problem("two_sum")
    names = DsaNames(
        function=NameMapping(original=p.entry_point, renamed="find_pair"),
        parameters=[
            NameMapping(original=param.name, renamed=new)
            for param, new in zip(p.signature.params, ["amounts", "goal"], strict=True)
        ],
    )
    return bank_task_spec(p, story, names, "python311", p.tiers[0])


def test_a_dsa_statement_with_original_names_is_rejected() -> None:
    good = renamed_dsa_spec("Find two expenses that add up to the goal.")
    bad = renamed_dsa_spec("Given nums, find two expenses that add up to the goal.")
    two_sum_profile = profile(**{good["tier"]: problem("two_sum").tags})

    _, good_reasons = run_gate(good, dsa_grade(good), gate_profile=two_sum_profile)
    _, bad_reasons = run_gate(bad, dsa_grade(bad), gate_profile=two_sum_profile)

    assert good_reasons == []
    assert codes(bad_reasons) == ["statement_names_leak"]
    assert bad_reasons[0]["items"] == ["nums"]


def test_the_renamed_reference_is_graded_with_the_new_names() -> None:
    spec = renamed_dsa_spec("Find two expenses.")
    grade = dsa_grade(spec)
    run_gate(spec, grade, gate_profile=profile(**{spec["tier"]: problem("two_sum").tags}))

    assert "def find_pair(amounts, goal):" in grade.graded_files[0]["solution.py"]


# --- Report field ---------------------------------------------------------------------


def test_report_mutation_score_is_null_for_pre_gate_certificates() -> None:
    legacy = TaskSpec.model_validate(
        domain_spec(
            certificate=draft_certificate(["app/utils.py"], True, True) | {"mutation_score": 0.0}
        )
    )
    gated = legacy.model_copy(
        update={
            "certificate": legacy.certificate.model_copy(
                update={"reference_pass": "4/4 x3", "mutation_score": 0.7}
            )
        }
    )

    assert (_mutation_score(legacy), _mutation_score(gated)) == (None, 0.7)


def test_check_reports_everything_it_found() -> None:
    spec = domain_spec(statement_md="Use `page - 1`.")
    spec["starter_files"]["app/services.py"] += "\nSTRAY = 1\n"
    report = check(
        spec, PROFILE, grade=FakeGrade(starter_fails={VISIBLE[0], OTHER_CONCEPT}), derive=same_ids
    )

    assert codes(report.reasons) == [
        "starter_breaks_other_concepts",
        "scope_files",
        "statement_leak",
    ]
    assert report.certificate is None
