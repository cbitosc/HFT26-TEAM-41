"""LLM enrichment (P2.5) with the LLM mocked: leak check, template fallback, renaming,
caching, extra tests, and the demo task left alone. No sandbox: test runs are faked."""

import ast
import json

import fakeredis
import httpx2
import pytest

from builder import enrich as e
from builder.manual import EXPENSES_SEED
from builder.tasks import load_seed, starter_base
from contracts_gen.run_result import RunResult, Summary
from contracts_gen.run_result import TestResult as RunTest
from gate import leak
from llm.client import LLMClient
from tests.test_llm_client import FakeFeatherless, make_settings, ok

FILES, CONCEPTS = load_seed(EXPENSES_SEED)
REFERENCE_LINE = "    offset = (page - 1) * page_size"
BUG_LINE = "    offset = page * page_size"
FAILING = [
    {
        "test": "tests/test_pagination.py::test_first_page_reports_total_and_has_next",
        "message": "AssertionError: assert ['e3', 'e4'] == ['e1', 'e2']",
    }
]
SAFE = e.Enrichment(
    title="Expense pages skip the first entries",
    statement="Page 1 of `GET /expenses` starts at the third expense instead of the first. "
    "Each page should hold the next `page_size` expenses, starting from the first one.",
    renames={},
)
LEAKY = e.Enrichment(
    title="Pagination offset bug",
    statement="Set `offset = (page - 1) * page_size` in paginate.",
    renames={},
)


def draft(tier: str = "novice", task_id: str = "py-fastapi-expenses-pagination-novice-0") -> dict:
    starter = starter_base(FILES)
    assert REFERENCE_LINE in starter["app/utils.py"]
    starter["app/utils.py"] = starter["app/utils.py"].replace(REFERENCE_LINE, BUG_LINE)
    return {
        "task_id": task_id,
        "tier": tier,
        "kind": "domain",
        "runtime": "python311",
        "seed_id": EXPENSES_SEED,
        "starter_files": starter,
        "target_symbols": ["app/utils.py::paginate"],
        "entry_symbols": ["app/utils.py::paginate", "app/schemas.py::ExpensePage"],
        "visible_tests": [],
        "hidden_tests": [],
        "statement_md": "TODO(P2.5)",
        "repo_tour_md": "",
        "reference_ref": f"seeds/{EXPENSES_SEED}",
        "perf": {"budget_ms": 442, "input_gen": "tests/perf/gen_large.py"},
        "certificate": {"scope_files": ["app/utils.py"]},
    }


class FakeLlm:
    def __init__(self, *answers: e.Enrichment) -> None:
        self.answers = list(answers)
        self.calls: list[list[dict]] = []

    def __call__(self, slot, messages, response_model, temperature, max_tokens):
        assert (slot, response_model, temperature) == ("generator", e.Enrichment, 0.2)
        assert max_tokens == e.STATEMENT_MAX_TOKENS
        self.calls.append(messages)
        return self.answers.pop(0)


def run_enrich(spec: dict, llm, **kwargs) -> e.Enriched:
    def no_rename_check(*args):
        raise AssertionError("no rename check expected")

    kwargs.setdefault("rename_check", no_rename_check)
    return e.enrich(
        spec, None, ["Shop backend"], llm=llm, failing_visible=lambda s: FAILING, **kwargs
    )


# --- Leak check -----------------------------------------------------------------------


def info() -> e.FixInfo:
    return e.fix_info({"app/utils.py": FILES["app/utils.py"]}, draft()["starter_files"])


def problems(statement: str) -> list[str]:
    """What enrich rejects a statement for: gate/leak.py's statement_problems."""
    found = info()
    return leak.statement_problems(statement, found.reference_lines, found.fragments)


def test_model_sees_the_starter_side_of_the_diff_only() -> None:
    diff = info().starter_diff

    assert "+" + BUG_LINE in diff
    assert "(page - 1)" not in diff  # the reference line never reaches the model


@pytest.mark.parametrize(
    "statement",
    [
        "Use offset = (page - 1) * page_size.",  # the reference line
        "The offset should use `(page-1)`.",  # the fixing tokens
    ],
)
def test_leak_check_catches_a_statement_containing_the_fix(statement) -> None:
    assert problems(statement)


def test_leak_check_passes_a_statement_of_symptoms() -> None:
    assert problems(f"{SAFE.title}\n{SAFE.statement}") == []


def test_leak_check_enforces_the_word_limit() -> None:
    assert problems("word " * 201) == ["longer than 200 words"]


# --- Statement ------------------------------------------------------------------------


def test_one_call_writes_the_statement_and_copies_the_tour() -> None:
    llm = FakeLlm(SAFE)

    result = run_enrich(draft(), llm)

    assert len(llm.calls) == 1
    assert result.statement_source == "llm"
    assert result.spec["statement_md"].startswith("### Expense pages skip the first entries")
    assert result.spec["repo_tour_md"] == FILES["README_TOUR.md"]
    sent = json.loads(llm.calls[0][1]["content"])
    assert sent["visible_failing_tests"] == FAILING
    assert sent["candidate_projects"] == ["Shop backend"]
    assert sent["renamable_terms"] == CONCEPTS["renamable"]


def test_a_rejected_statement_is_retried_once() -> None:
    llm = FakeLlm(LEAKY, SAFE)

    result = run_enrich(draft(), llm)

    assert result.statement_source == "llm_retry"
    assert llm.calls[1][-1]["content"].startswith("Rejected: ")


def test_template_is_used_after_two_failures() -> None:
    llm = FakeLlm(LEAKY, LEAKY)

    result = run_enrich(draft(), llm)

    assert len(llm.calls) == 2
    assert result.statement_source == "template"
    assert result.rejections
    statement = result.spec["statement_md"]
    assert "test_first_page_reports_total_and_has_next" in statement
    assert problems(statement) == []


def test_master_budget_sentence_is_appended_by_code() -> None:
    spec = draft("master") | {
        "target_symbols": ["app/utils.py::paginate", "app/services.py::import_expenses"]
    }

    statement = run_enrich(spec, FakeLlm(SAFE)).spec["statement_md"]

    assert statement.endswith("within 442 ms; slower code loses up to half of this task's score.")


def test_demo_task_is_untouched() -> None:
    spec = draft(task_id="expenses-pagination")
    llm = FakeLlm()

    result = run_enrich(spec, llm)

    assert result.spec is spec
    assert llm.calls == []


def test_a_cache_hit_makes_no_second_call() -> None:
    api = FakeFeatherless()
    api.queue(ok(SAFE.model_dump_json(), prompt_tokens=900, completion_tokens=120))
    http = httpx2.Client(transport=httpx2.MockTransport(api.handler))
    client = LLMClient(make_settings(), fakeredis.FakeRedis(decode_responses=True), http)

    hits = []

    def llm(slot, messages, response_model, temperature, max_tokens):
        result, call = client.structured(
            slot, messages, response_model, temperature=temperature, max_tokens=max_tokens
        )
        hits.append(call.cache_hit)
        return result

    first = run_enrich(draft(), llm)
    second = run_enrich(draft(), llm)

    assert len(api.requests) == 1
    assert api.requests[0]["max_tokens"] == 500 and api.requests[0]["temperature"] == 0.2
    assert hits == [False, True]
    assert first.spec["statement_md"] == second.spec["statement_md"]


def test_an_llm_failure_falls_back_to_the_template() -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("budget exceeded")

    result = run_enrich(draft(), broken)

    assert result.statement_source == "template"
    assert result.notes and "attempt 1 failed" in result.notes[0]


# --- Renaming -------------------------------------------------------------------------

RENAMES = {"expense": "order", "category": "department"}


def test_rename_text_handles_case_plural_and_compound_names() -> None:
    text = "Expense expenses_of ExpenseCreate /expenses categories Category.FOOD subcategory"

    assert e.rename_text(text, RENAMES) == (
        "Order orders_of OrderCreate /orders departments Department.FOOD subcategory"
    )


def test_renamed_code_stays_valid_python() -> None:
    spec = e.renamed_spec(draft(), RENAMES)

    for path, source in spec["starter_files"].items():
        if path.endswith(".py"):
            ast.parse(source)
    services = spec["starter_files"]["app/services.py"]
    assert "def import_orders(" in services and "Expense" not in services
    assert spec["entry_symbols"] == ["app/utils.py::paginate", "app/schemas.py::OrderPage"]
    assert (
        spec["reference_ref"] == f"seeds/{EXPENSES_SEED}?rename=category:department,expense:order"
    )
    assert (
        "class Order(Base)"
        in e.reference_files(spec | {"certificate": {"scope_files": ["app/models.py"]}})[
            "app/models.py"
        ]
    )


def test_rename_map_is_limited_to_the_renamable_terms() -> None:
    renames, dropped = e.valid_renames(
        {"expense": "Order", "amount": "price", "category": "sort"},
        CONCEPTS["renamable"],
        starter_base(FILES),
    )

    assert renames == {"expense": "order"}
    assert any("amount: not a renamable term" in d for d in dropped)
    assert any("category -> sort: clashes" in d for d in dropped)


def test_renaming_is_applied_when_the_check_passes() -> None:
    llm = FakeLlm(SAFE.model_copy(update={"renames": RENAMES}))
    seen = {}

    def check(original, renamed, renames):
        seen["renames"] = renames
        return renamed | {"visible_test_ids": ["x"]}, "applied"

    result = run_enrich(draft(), llm, rename_check=check)

    assert seen["renames"] == RENAMES
    assert result.renames == RENAMES and result.rename_status == "applied"
    assert result.spec["statement_md"].startswith("### Order pages skip the first entries")


def test_renaming_is_dropped_when_results_differ() -> None:
    llm = FakeLlm(SAFE.model_copy(update={"renames": RENAMES}))

    result = run_enrich(
        draft(), llm, rename_check=lambda *args: (None, "dropped: results differ (starter.hidden)")
    )

    assert result.renames == {}
    assert result.rename_status.startswith("dropped")
    assert "def import_expenses(" in result.spec["starter_files"]["app/services.py"]
    assert result.spec["reference_ref"] == f"seeds/{EXPENSES_SEED}"


# --- Extra hidden tests (flag) --------------------------------------------------------

EXTRA = """from app.utils import month_bounds


def test_good():
    assert month_bounds(2026, 1)[0].day == 1


def test_wrong():
    assert False
"""


def test_extra_tests_are_off_by_default_and_keep_only_reference_passing_ones(monkeypatch):
    assert run_enrich(draft(), FakeLlm(SAFE)).spec["hidden_tests"] == []

    def fake_run(runtime, files, paths, timeout):
        tests = [
            RunTest(
                id=f"{e.EXTRA_TESTS_PATH}::{name}",
                name=name,
                outcome=outcome,
                duration_ms=1,
                message=None,
            )
            for name, outcome in (("test_good", "passed"), ("test_wrong", "failed"))
        ]
        return RunResult(
            status="ok",
            reason=None,
            duration_ms=1,
            tests=tests,
            summary=Summary(passed=1, failed=1, total=2),
            stdout_tail="",
            stderr_tail="",
        )

    def extra_llm(slot, messages, response_model, temperature, max_tokens):
        assert response_model is e.ExtraTests
        return e.ExtraTests(module=EXTRA)

    monkeypatch.setattr(e.grading, "derive_test_ids", lambda spec: spec)
    spec, kept = e.extra_hidden_tests(draft(), extra_llm, run=fake_run)

    assert kept == 1
    [added] = [t for t in spec["hidden_tests"] if t["path"] == e.EXTRA_TESTS_PATH]
    assert "def test_good" in added["content"] and "def test_wrong" not in added["content"]
