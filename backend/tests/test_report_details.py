"""Report details (F3): claim map, timeline, integrity notes, efficiency parts, AI summary."""

import copy
from types import SimpleNamespace

import pytest

from app import grading, recruiter
from app.models import Event
from contracts_gen.profile import Profile
from contracts_gen.task_spec import TaskSpec
from report import build, summary
from report.claims import claim_map, concept_of, verdict
from scoring import efficiency as eff
from tests.api_support import LEAK_MARKER, dsa_spec
from tests.grading_support import FIXED, FakeRunner
from tests.test_scores_api import TASK, start_session, submit_fixed

T0 = 1_900_000_000_000


@pytest.fixture
def runner(monkeypatch) -> FakeRunner:
    fake = FakeRunner()
    monkeypatch.setattr(grading, "run_tests", fake)
    return fake


def profile(**overrides) -> Profile:
    data = {
        "domain": "backend",
        "runtime": "python311",
        "concepts": ["pagination", "caching"],
        "topics_solved": {"sliding_window": 14, "trees": 19},
        "allowed_topics": {"novice": [], "adept": [], "master": []},
        "suggested_tier": "novice",
        "tier_reason": "test",
        "unsupported_notes": [],
        "sources": {"domain": "rules", "runtime": "rules", "concepts": "rules"},
    }
    return Profile.model_validate(data | overrides)


def domain(task_id: str = "expenses-pagination", targets=("app/utils.py::paginate",)) -> TaskSpec:
    spec = copy.deepcopy(dsa_spec())  # any valid spec; turned into a seed domain task below
    spec.update(
        task_id=task_id,
        kind="domain",
        seed_id="py-fastapi-expenses",
        runtime="python311",
        dsa_tags=[],
        dsa_cases=None,
        dsa_names=None,
        target_symbols=list(targets),
        entry_symbols=list(targets),
    )
    return TaskSpec.model_validate(spec)


def dsa(tags=("sliding_window",)) -> TaskSpec:
    spec = copy.deepcopy(dsa_spec())
    spec.update(task_id="dsa-1", dsa_tags=list(tags), runtime="python311")
    return TaskSpec.model_validate(spec)


# --- Claim map ------------------------------------------------------------------------


def test_concept_of_reads_the_task_id_then_the_symbols() -> None:
    assert concept_of(domain()) == "pagination"
    assert concept_of(domain("py-fastapi-expenses-reporting-adept", ())) == "reporting"
    assert concept_of(domain("custom-task", ("app/utils.py::paginate",))) == "pagination"
    assert concept_of(dsa()) is None


def test_each_claim_gets_the_tasks_that_tested_it_and_a_verdict() -> None:
    claims = claim_map(profile(), [domain(), dsa()], {"expenses-pagination": 100.0, "dsa-1": 50.0})

    rows = {(c.kind, c.claim): (c.tested_by, c.correctness, c.verdict) for c in claims}
    assert rows[("concept", "pagination")] == (["expenses-pagination"], 100.0, "verified")
    assert rows[("concept", "caching")] == ([], None, "not_tested")
    assert rows[("dsa_topic", "sliding window")] == (["dsa-1"], 50.0, "partly")
    assert rows[("dsa_topic", "trees")][2] == "not_tested"
    assert rows[("runtime", "Python")] == (["expenses-pagination", "dsa-1"], 75.0, "partly")
    assert next(c for c in claims if c.claim == "trees").evidence == "19 problems solved"


def test_verdict_thresholds() -> None:
    assert [verdict(v) for v in (None, 80, 79.9, 45, 44.9)] == [
        "not_tested",
        "verified",
        "partly",
        "partly",
        "not_verified",
    ]


# --- Timeline and integrity -----------------------------------------------------------


def event(kind: str, ts: int, payload: dict, task_id: str = TASK) -> Event:
    return Event(task_id=task_id, ts=ts, type=kind, payload=payload)


def run_payload(visible: int, hidden: int) -> dict:
    return {
        "visible": {"passed": visible, "total": 2},
        "hidden_silent": {"passed": hidden, "total": 4, "failing_ids": []},
    }


def test_timeline_has_hidden_progress_and_hint_markers() -> None:
    events = [
        event("run", T0 + 60_000, run_payload(0, 1)),
        event(
            "hint_response",
            T0 + 90_000,
            {"level": 1, "mentions": [], "similarity": 0, "blocked": False},
        ),
        event("run", T0 + 120_000, run_payload(2, 4)),
        event(
            "submit",
            T0 + 180_000,
            {
                "visible": {"passed": 2, "total": 2},
                "hidden": {"passed": 4, "total": 4},
                "perf_ms": None,
                "final": True,
            },
        ),
    ]

    [line] = build.timelines(T0, [domain(TASK)], events)

    assert [(p.minute, p.kind, p.hidden_rate) for p in line.points] == [
        (1.0, "run", 0.25),
        (2.0, "run", 1.0),
        (3.0, "submit", 1.0),
    ]
    assert [(h.minute, h.level) for h in line.hints] == [(1.5, 1)]


def test_integrity_notes_count_pastes_blurs_flags_and_refused_writes() -> None:
    events = [
        event("hint_response", T0, {"level": 2, "mentions": [], "similarity": 0, "blocked": False}),
        event("paste", T0 + 30_000, {"chars": 500}),
        event("paste", T0 + 10 * 60_000, {"chars": 20}),
        event("blur", T0 + 1000, {}),
        event("blur", T0 + 2000, {}),
        event("hint_request", T0 + 3000, {"level_allowed": 1, "flagged_extraction": True}),
    ]
    flag = {"path": "app/x.py", "line": 3, "rule": "network", "excerpt": "import socket"}
    runs = [
        SimpleNamespace(task_id=TASK, integrity={"flags": [flag], "dropped_paths": ["tests/t.py"]}),
        SimpleNamespace(task_id=TASK, integrity={"flags": [flag], "dropped_paths": []}),
    ]

    notes = build.integrity(T0, events, runs)

    assert [(p.chars, p.large, p.after_hint) for p in notes.pastes] == [
        (500, True, True),
        (20, False, False),
    ]
    assert (notes.paste_chars, notes.blurs, notes.extraction_attempts) == (520, 2, 1)
    assert notes.flags == [{"task_id": TASK, **flag}]  # the same flag on two runs counts once
    assert notes.refused_writes == ["tests/t.py"]


def test_efficiency_breakdown_lists_the_weighted_parts() -> None:
    e = eff.Efficiency(0.7, pph=1.0, td=0.5, freq=1.0, ind=0.75, extraction_attempts=1)

    out = build.efficiency_breakdown(e, hints=2, mean_correctness=40)

    assert [(p.weight, p.value) for p in out.parts] == [
        (0.35, 1.0),
        (0.2, 0.5),
        (0.15, 1.0),
        (0.3, 0.75),
    ]
    assert out.scale == 0.8 and out.hints == 2 and out.extraction_attempts == 1


# --- Summary --------------------------------------------------------------------------


def test_first_sentences_keeps_four() -> None:
    text = "One. Two!  Three?\nFour. Five."

    assert summary.first_sentences(text) == "One. Two! Three? Four."


# --- API ------------------------------------------------------------------------------


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(
        recruiter, "get_settings", lambda: SimpleNamespace(recruiter_api_key="secret")
    )
    return {"X-Recruiter-Key": "secret"}


def test_report_needs_the_key_and_a_graded_session(db, http, key, runner) -> None:
    session_id = start_session(db)

    assert http.get(f"/sessions/{session_id}/report").status_code == 401
    assert http.get(f"/sessions/{session_id}/report", headers=key).status_code == 409
    submit_fixed(db, session_id)
    body = http.get(f"/sessions/{session_id}/report", headers=key).json()

    assert body["breakdown"]["final_score"] == 100.0
    assert [c["task_id"] for c in body["certificates"]] == [TASK]
    assert {c["kind"] for c in body["claims"]} >= {"runtime"}
    assert body["efficiency"] is None  # novice: no assistant
    assert body["timelines"][0]["points"][-1]["kind"] == "submit"
    assert LEAK_MARKER not in str(body)  # no hidden test ids or contents


def test_summary_is_one_generator_call_over_numbers_only(
    db, http, key, runner, monkeypatch
) -> None:
    session_id = start_session(db)
    submit_fixed(db, session_id)
    calls = []

    def fake(slot, messages, temperature, max_tokens):
        calls.append((slot, messages, max_tokens))
        return "S1. S2. S3. S4. S5 is cut."

    monkeypatch.setattr(summary, "complete_text", fake)
    body = http.get(f"/sessions/{session_id}/report/summary", headers=key).json()

    assert body == {"summary": "S1. S2. S3. S4.", "label": "AI summary, not scored"}
    [(slot, messages, max_tokens)] = calls
    assert (slot, max_tokens) == ("generator", 300)
    sent = str(messages)
    assert FIXED not in sent and "return a" not in sent  # numbers, not code
    assert LEAK_MARKER not in sent


def test_summary_is_503_when_the_model_fails(db, http, key, runner, monkeypatch) -> None:
    session_id = start_session(db)
    submit_fixed(db, session_id)

    def broken(*args, **kwargs):
        raise RuntimeError("budget exceeded")

    monkeypatch.setattr(summary, "complete_text", broken)

    assert http.get(f"/sessions/{session_id}/report/summary", headers=key).status_code == 503
