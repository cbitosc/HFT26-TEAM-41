"""Replay a task's focus and edit events onto its function graph, and the Trail metrics.

Focus events are sampled once per second while the editor has focus (frontend
lib/telemetry.ts), so each sample is SAMPLE_MS of dwell. A sample's line is mapped with
the candidate's file as it was then (the latest saved snapshot, else the starter), so
lines added above a function don't shift the trail. Edits carry no line: an edit goes to
the function under the cursor of the latest focus sample in that file.

Metrics (report-only, never scored):
    time_to_target_ms  first focus on a target symbol, from the task's first focus
    off_path_ms        dwell outside the targets before that first visit
    found              "independent", "after_hint" (first visit within FOUND_AFTER_HINT_MS
                       after a hint on the task) or "not_found"
    edit_precision     share of the lines changed from the starter to the final files that
                       lie inside a target symbol (None without changes)
"""

import bisect
import difflib
from dataclasses import dataclass, field
from typing import Literal

from trail.graph import Span, call_edges, node_at, spans

SAMPLE_MS = 1000
VISIT_GAP_MS = 5000
"""A pause longer than this between samples on the same node starts a new visit."""
FOUND_AFTER_HINT_MS = 2 * 60_000


@dataclass(frozen=True)
class Focus:
    ts: int
    file: str
    line: int


@dataclass(frozen=True)
class Edit:
    ts: int
    file: str
    chars: int


@dataclass(frozen=True)
class Hint:
    ts: int
    level: int
    blocked: bool


@dataclass
class Node:
    id: str
    file: str
    name: str
    target: bool
    start: int | None = None
    end: int | None = None
    dwell_ms: int = 0


@dataclass(frozen=True)
class Visit:
    node: str
    start_ms: int
    end_ms: int
    after_hint: bool


@dataclass(frozen=True)
class EditMark:
    ts: int
    node: str
    chars: int


@dataclass(frozen=True)
class Metrics:
    time_to_target_ms: int | None
    off_path_ms: int
    found: Literal["independent", "after_hint", "not_found"]
    edit_precision: float | None
    lines_changed: int
    functions_visited: int
    hints: int


@dataclass
class TaskTrail:
    task_id: str
    kind: str
    targets: list[str]
    nodes: list[Node]
    edges: list[tuple[str, str]]
    visits: list[Visit]
    edits: list[EditMark]
    hints: list[Hint]
    metrics: Metrics
    first_ms: int | None = None
    last_ms: int | None = None
    files: list[str] = field(default_factory=list)


class _SpanTimeline:
    """Spans of each file as of a moment: the latest parsable snapshot, else the starter."""

    def __init__(self, starter: dict[str, str], snapshots: list[tuple[int, dict[str, str]]]):
        self.starter_source = starter
        self.starter = {p: spans(p, s) or [] for p, s in starter.items()}
        self.snapshots = sorted(snapshots, key=lambda item: item[0])
        self._cache: dict[tuple[int, str], list[Span] | None] = {}

    def at(self, ts: int, path: str) -> tuple[list[Span], str | None]:
        """(spans, source) of `path` as of `ts`."""
        for index in range(len(self.snapshots) - 1, -1, -1):
            snap_ts, files = self.snapshots[index]
            if snap_ts > ts or path not in files:
                continue
            key = (index, path)
            if key not in self._cache:
                self._cache[key] = spans(path, files[path])
            if self._cache[key] is not None:
                return self._cache[key], files[path]
        return self.starter.get(path, []), self.starter_source.get(path)


def _changed_lines(starter: dict[str, str], final: dict[str, str]) -> list[str]:
    """One node id per line changed from the starter to the final files."""
    out = []
    for path in sorted(set(starter) | set(final)):
        before = starter.get(path, "").splitlines()
        after = final.get(path, starter.get(path, "")).splitlines()
        before_spans = spans(path, starter.get(path, "")) or []
        after_spans = spans(path, final.get(path, "")) if path in final else before_spans
        after_spans = before_spans if after_spans is None else after_spans
        matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                continue
            if j2 > j1:
                out += [node_at(after_spans, path, j + 1) for j in range(j1, j2)]
            else:
                out += [node_at(before_spans, path, i + 1) for i in range(i1, i2)]
    return out


def build_trail(
    task_id: str,
    kind: str,
    starter: dict[str, str],
    targets: list[str],
    focus: list[Focus],
    edits: list[Edit],
    snapshots: list[tuple[int, dict[str, str]]],
    hints: list[Hint],
    final: dict[str, str],
) -> TaskTrail:
    """The trail of one task. `starter`/`final`/`snapshots`: the task's code files only."""
    focus = sorted(focus, key=lambda f: f.ts)
    hints = sorted(hints, key=lambda h: h.ts)
    timeline = _SpanTimeline(starter, snapshots)
    target_set = set(targets)

    nodes: dict[str, Node] = {}
    for path in sorted(starter):
        nodes[path] = Node(path, path, "(module)", path in target_set)
        for span in timeline.starter[path]:
            nodes[span.id] = Node(
                span.id, path, span.name, span.id in target_set, span.start, span.end
            )

    def node_for(ts: int, path: str, line: int) -> str:
        file_spans, source = timeline.at(ts, path)
        node_id = node_at(file_spans, path, line, source)
        if node_id not in nodes:  # a function the candidate added, or a file outside the starter
            name = node_id.split("::", 1)[1] if "::" in node_id else "(module)"
            nodes[node_id] = Node(node_id, path, name, node_id in target_set)
            if path not in nodes:
                nodes[path] = Node(path, path, "(module)", path in target_set)
        return node_id

    visits: list[Visit] = []
    samples: list[tuple[int, str]] = []
    for sample in focus:
        node_id = node_for(sample.ts, sample.file, sample.line)
        nodes[node_id].dwell_ms += SAMPLE_MS
        samples.append((sample.ts, node_id))
        last = visits[-1] if visits else None
        if last and last.node == node_id and sample.ts - last.end_ms <= VISIT_GAP_MS:
            visits[-1] = Visit(node_id, last.start_ms, sample.ts + SAMPLE_MS, last.after_hint)
        else:
            after_hint = any(h.ts <= sample.ts for h in hints)
            visits.append(Visit(node_id, sample.ts, sample.ts + SAMPLE_MS, after_hint))

    by_file: dict[str, list[Focus]] = {}
    for sample in focus:
        by_file.setdefault(sample.file, []).append(sample)
    times = {path: [f.ts for f in samples_] for path, samples_ in by_file.items()}
    marks = []
    for edit in sorted(edits, key=lambda e: e.ts):
        index = bisect.bisect_right(times.get(edit.file, []), edit.ts + SAMPLE_MS)
        line = by_file[edit.file][index - 1].line if index else 0
        node_id = node_for(edit.ts, edit.file, line) if line else edit.file
        if node_id not in nodes:
            nodes[node_id] = Node(node_id, edit.file, "(module)", node_id in target_set)
        marks.append(EditMark(edit.ts, node_id, edit.chars))

    first_target = next((ts for ts, node_id in samples if node_id in target_set), None)
    first_ms = samples[0][0] if samples else None
    off_path = sum(
        SAMPLE_MS
        for ts, node_id in samples
        if node_id not in target_set and (first_target is None or ts < first_target)
    )
    found: Literal["independent", "after_hint", "not_found"] = "not_found"
    if first_target is not None:
        helped = any(h.ts <= first_target <= h.ts + FOUND_AFTER_HINT_MS for h in hints)
        found = "after_hint" if helped else "independent"
    changed = _changed_lines(starter, final)
    precision = None if not changed else sum(n in target_set for n in changed) / len(changed)
    metrics = Metrics(
        time_to_target_ms=None if first_target is None else first_target - first_ms,
        off_path_ms=off_path,
        found=found,
        edit_precision=None if precision is None else round(precision, 4),
        lines_changed=len(changed),
        functions_visited=len({n for _, n in samples if "::" in n}),
        hints=len(hints),
    )
    all_spans = [s for file_spans in timeline.starter.values() for s in file_spans]
    return TaskTrail(
        task_id=task_id,
        kind=kind,
        targets=targets,
        nodes=list(nodes.values()),
        edges=call_edges(starter, all_spans),
        visits=visits,
        edits=marks,
        hints=hints,
        metrics=metrics,
        first_ms=first_ms,
        last_ms=samples[-1][0] + SAMPLE_MS if samples else None,
        files=sorted({n.file for n in nodes.values()}),
    )
