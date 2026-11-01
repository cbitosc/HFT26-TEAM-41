"""Trail Map (F4): spans and call graph, replay and metrics, and the recruiter-keyed API."""

from types import SimpleNamespace

import pytest

from app import recruiter
from app.models import Event, FileSnapshot
from tests.grading_support import FIXED
from tests.test_scores_api import TASK, start_session
from trail import graph
from trail.replay import Edit, Focus, Hint, build_trail

SERVICES = '''"""Services."""


def list_items(user):
    return paginate(query(user))


def query(user):
    return [user]


class Report:
    def total(self, rows):
        return sum(rows)

    def run(self, rows):
        return self.total(rows)
'''
UTILS = """def paginate(rows):
    return rows[:10]
"""
FILES = {"app/services.py": SERVICES, "app/utils.py": UTILS}
TARGET = "app/utils.py::paginate"
T0 = 1_900_000_000_000


# --- Graph ----------------------------------------------------------------------------


def test_spans_cover_functions_and_methods() -> None:
    found = {(s.id, s.start, s.end) for s in graph.spans("app/services.py", SERVICES)}

    assert found == {
        ("app/services.py::list_items", 4, 5),
        ("app/services.py::query", 8, 9),
        ("app/services.py::Report.total", 13, 14),
        ("app/services.py::Report.run", 16, 17),
    }
    assert graph.spans("app/broken.py", "def f(:\n") is None
    assert graph.spans("solution.js", "function f() {}") == []


def test_lines_map_to_the_innermost_function_or_the_file() -> None:
    file_spans = graph.spans("app/services.py", SERVICES)

    assert graph.node_at(file_spans, "app/services.py", 5) == "app/services.py::list_items"
    assert graph.node_at(file_spans, "app/services.py", 1) == "app/services.py"


def test_blank_lines_after_a_function_belong_to_it() -> None:
    stub = "def solve(s):\n    return 0\n"
    file_spans = graph.spans("solution.py", stub)

    # Line 3: the empty line after the final newline, where Monaco leaves the cursor.
    assert graph.node_at(file_spans, "solution.py", 3, stub) == "solution.py::solve"
    assert graph.node_at(file_spans, "solution.py", 3) == "solution.py"  # without source
    # Code between functions doesn't: line 6 is `x = 1`, line 7 a blank after it.
    two = "def a():\n    pass\n\n\nx = 1\n\ndef b():\n    pass\n"
    two_spans = graph.spans("m.py", two)
    assert graph.node_at(two_spans, "m.py", 3, two) == "m.py::a"
    assert graph.node_at(two_spans, "m.py", 6, two) == "m.py"


def test_call_edges_are_by_name_and_prefer_the_callers_file() -> None:
    all_spans = [s for p, src in FILES.items() for s in graph.spans(p, src)]

    assert graph.call_edges(FILES, all_spans) == [
        ("app/services.py::Report.run", "app/services.py::Report.total"),
        ("app/services.py::list_items", "app/services.py::query"),
        ("app/services.py::list_items", "app/utils.py::paginate"),
    ]


# --- Replay and metrics ---------------------------------------------------------------


def trail(focus, edits=(), snapshots=(), hints=(), final=None):
    return build_trail(
        TASK,
        "domain",
        FILES,
        [TARGET],
        list(focus),
        list(edits),
        list(snapshots),
        list(hints),
        final or FILES,
    )


def seconds(start_s: int, n: int, file: str, line: int) -> list[Focus]:
    return [Focus(T0 + (start_s + i) * 1000, file, line) for i in range(n)]


def test_visits_dwell_and_an_independent_find() -> None:
    focus = seconds(0, 3, "app/services.py", 5) + seconds(3, 2, "app/utils.py", 2)

    t = trail(focus)

    assert [(v.node, v.end_ms - v.start_ms) for v in t.visits] == [
        ("app/services.py::list_items", 3000),
        (TARGET, 2000),
    ]
    dwell = {n.id: n.dwell_ms for n in t.nodes}
    assert dwell["app/services.py::list_items"] == 3000 and dwell[TARGET] == 2000
    assert t.metrics.time_to_target_ms == 3000
    assert t.metrics.off_path_ms == 3000
    assert t.metrics.found == "independent"
    assert t.metrics.functions_visited == 2
    assert t.metrics.edit_precision is None and t.metrics.lines_changed == 0
    assert next(n for n in t.nodes if n.id == TARGET).target


def test_a_long_pause_splits_a_visit() -> None:
    focus = seconds(0, 2, "app/utils.py", 2) + seconds(20, 1, "app/utils.py", 2)

    assert len(trail(focus).visits) == 2


def test_lines_follow_the_candidates_file_as_it_was_then() -> None:
    # The candidate added 3 lines at the top: line 5 is now inside paginate.
    shifted = "import math\n\n\n" + UTILS
    snapshot = (T0 + 500, {"app/utils.py": shifted})

    t = trail(seconds(1, 1, "app/utils.py", 5), snapshots=[snapshot])

    assert t.visits[0].node == TARGET


def test_finding_the_target_within_two_minutes_of_a_hint() -> None:
    hint = Hint(T0 + 10_000, 1, False)
    focus = seconds(0, 5, "app/services.py", 9) + seconds(60, 1, "app/utils.py", 2)

    t = trail(focus, hints=[hint])

    assert t.metrics.found == "after_hint"
    assert [v.after_hint for v in t.visits] == [False, True]
    assert trail(seconds(0, 1, "app/services.py", 5)).metrics.found == "not_found"


def test_edits_go_to_the_function_under_the_cursor_and_precision_counts_lines() -> None:
    focus = seconds(0, 2, "app/utils.py", 2)
    edits = [Edit(T0 + 1000, "app/utils.py", 4)]
    final = {
        "app/services.py": SERVICES.replace("return [user]", "return [user, user]"),
        "app/utils.py": UTILS.replace("rows[:10]", "rows[:20]"),
    }

    t = trail(focus, edits=edits, final=final)

    assert [(e.node, e.chars) for e in t.edits] == [(TARGET, 4)]
    assert t.metrics.lines_changed == 2
    assert t.metrics.edit_precision == 0.5  # one of the two changed lines is in the target


# --- API ------------------------------------------------------------------------------


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(
        recruiter, "get_settings", lambda: SimpleNamespace(recruiter_api_key="secret")
    )
    return {"X-Recruiter-Key": "secret"}


def test_trail_needs_the_recruiter_key(db, http, monkeypatch) -> None:
    session_id = start_session(db, tier="novice")
    url = f"/sessions/{session_id}/trail"
    monkeypatch.setattr(recruiter, "get_settings", lambda: SimpleNamespace(recruiter_api_key=""))
    assert http.get(url).status_code == 503  # fails closed without a configured key
    monkeypatch.setattr(
        recruiter, "get_settings", lambda: SimpleNamespace(recruiter_api_key="secret")
    )
    assert http.get(url).status_code == 401
    assert http.get(url, headers={"X-Recruiter-Key": "wrong"}).status_code == 401
    assert http.get(url, headers={"X-Recruiter-Key": "secret"}).status_code == 200


def test_trail_of_a_session(db, http, key) -> None:
    import uuid
    from datetime import UTC, datetime

    session_id = start_session(db, tier="novice")
    for i in range(3):
        payload = {"file": "app/calc.py", "line": 2, "symbol": None}
        db.add(
            Event(
                session_id=session_id, task_id=TASK, ts=T0 + i * 1000, type="focus", payload=payload
            )
        )
    db.add(
        FileSnapshot(
            session_id=session_id,
            task_id=TASK,
            ts=datetime.fromtimestamp((T0 + 5000) / 1000, UTC),
            files={"app/calc.py": FIXED},
        )
    )
    db.flush()

    body = http.get(f"/sessions/{session_id}/trail", headers=key).json()

    [task] = body["tasks"]
    assert task["targets"] == ["app/calc.py::add"]
    assert {n["id"] for n in task["nodes"]} >= {"app/calc.py", "app/calc.py::add"}
    assert task["visits"] == [
        {"node": "app/calc.py::add", "start_ms": T0, "end_ms": T0 + 3000, "after_hint": False}
    ]
    assert task["metrics"]["found"] == "independent"
    assert task["metrics"]["time_to_target_ms"] == 0
    assert task["metrics"]["edit_precision"] == 1.0
    assert http.get(f"/sessions/{uuid.uuid4()}/trail", headers=key).status_code == 404
