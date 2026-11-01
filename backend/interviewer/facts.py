"""What the candidate changed in each task, and the facts an explanation of it should mention.

Plain code, no model. A task's change is the candidate's last saved editable files against
the editable starter files (never the reference). Facts are the changed file and the
functions around the changed lines (plus the topic of a DSA task); an answer mentions a
fact when one of its keywords appears, by normalized keyword or fuzzy match. Report only:
"x of y facts" is shown next to the transcript and never scored (CLAUDE.md rule 8).
"""

import ast
import difflib
import re
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssessmentSession, FileSnapshot, Task
from app.workspace import split_editable
from contracts_gen.task_spec import TaskSpec

MAX_FACTS = 3
DIFF_LINES = 60
FUZZY_RATIO = 0.82
STEM_CHARS = 5
_WORD = re.compile(r"[a-z0-9]+")
_JS_FUNCTION = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)|^\s*(?:const|let|var)\s+(\w+)\s*=\s*"
    r"(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|\w+\s*=>)|^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{"
)
_JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return"}
GENERIC_STEMS = {"index", "main", "app", "solution", "__init__"}


@dataclass(frozen=True)
class Fact:
    label: str
    """Shown in the report, e.g. "function paginate"."""
    keywords: list[str]
    """Any of these in an answer counts as mentioning the fact."""


@dataclass(frozen=True)
class TaskChange:
    task_id: str
    kind: str
    title: str
    files: list[str]
    functions: list[str]
    diff: str
    """Unified diff of the candidate's editable code, at most DIFF_LINES lines."""
    facts: list[Fact] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _title(spec: TaskSpec) -> str:
    for line in spec.statement_md.splitlines():
        if line.strip():
            return line.lstrip("# ").strip()[:120]
    return spec.task_id


def _python_functions(text: str) -> list[tuple[str, int, int]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            spans.append((node.name, node.lineno, node.end_lineno or node.lineno))
    return spans


def _js_functions(text: str) -> list[tuple[str, int, int]]:
    """Rough spans: each function runs until the next function's first line."""
    starts = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = _JS_FUNCTION.match(line)
        name = match and next((g for g in match.groups() if g), None)
        if name and name not in _JS_KEYWORDS:
            starts.append((name, number))
    ends = [n - 1 for _, n in starts[1:]] + [len(text.splitlines())]
    return [(name, start, end) for (name, start), end in zip(starts, ends, strict=True)]


def changed_functions(path: str, before: str, after: str) -> list[str]:
    """Names of the innermost functions in `after` whose lines changed against `before`."""
    a = [line.strip() for line in before.splitlines()]
    b = [line.strip() for line in after.splitlines()]
    changed: set[int] = set()
    for op, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op != "equal":
            changed.update(range(j1 + 1, max(j2, j1 + 1) + 1))
    spans = _python_functions(after) if path.endswith(".py") else _js_functions(after)
    names: list[str] = []
    for line in sorted(changed):
        inside = [s for s in spans if s[1] <= line <= s[2]]
        if inside:
            name = min(inside, key=lambda s: s[2] - s[1])[0]
            if name not in names:
                names.append(name)
    return names


def _unified(path: str, before: str, after: str) -> list[str]:
    lines = difflib.unified_diff(
        before.splitlines(), after.splitlines(), f"a/{path}", f"b/{path}", lineterm="", n=1
    )
    return list(lines)


def _final_files(db: Session, session: AssessmentSession, spec: TaskSpec) -> dict[str, str]:
    query = select(FileSnapshot).where(
        FileSnapshot.session_id == session.id, FileSnapshot.task_id == spec.task_id
    )
    if session.submitted_at is not None:
        query = query.where(FileSnapshot.ts <= session.submitted_at)
    snapshot = db.scalars(query.order_by(FileSnapshot.ts.desc(), FileSnapshot.id.desc())).first()
    starter, _ = split_editable(spec, spec.starter_files)
    saved, _ = split_editable(spec, snapshot.files if snapshot else {})
    return starter | saved


def task_change(spec: TaskSpec, final: dict[str, str]) -> TaskChange:
    starter, _ = split_editable(spec, spec.starter_files)
    files, functions, diff_lines = [], [], []
    for path in sorted(set(starter) | set(final)):
        before, after = starter.get(path, ""), final.get(path, "")
        if before.strip() == after.strip():
            continue
        files.append(path)
        functions += [f for f in changed_functions(path, before, after) if f not in functions]
        diff_lines += _unified(path, before, after)
    change = TaskChange(
        task_id=spec.task_id,
        kind=spec.kind,
        title=_title(spec),
        files=files,
        functions=functions,
        diff="\n".join(diff_lines[:DIFF_LINES]),
    )
    return TaskChange(**{**asdict(change), "facts": facts_for(change, spec)})


def facts_for(change: TaskChange, spec: TaskSpec) -> list[Fact]:
    facts: list[Fact] = []
    for name in change.functions[:2]:
        facts.append(Fact(f"function {name}", [name]))
    for path in change.files:
        stem = PurePosixPath(path).stem
        if stem not in GENERIC_STEMS and len(facts) < MAX_FACTS:
            facts.append(Fact(f"file {path}", [stem]))
            break
    if spec.kind == "dsa" and spec.dsa_tags and len(facts) < MAX_FACTS:
        topic = spec.dsa_tags[0].replace("_", " ")
        facts.append(Fact(f"approach: {topic}", [topic]))
    return facts[:MAX_FACTS]


def session_changes(db: Session, session: AssessmentSession) -> list[TaskChange]:
    tasks = db.scalars(
        select(Task).where(Task.assessment_id == session.assessment_id).order_by(Task.order)
    ).all()
    changes = []
    for task in tasks:
        spec = TaskSpec.model_validate(task.spec)
        changes.append(task_change(spec, _final_files(db, session, spec)))
    return changes


# --- Matching -------------------------------------------------------------------------


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _parts(keyword: str) -> list[str]:
    """`paginateItems`, `paginate_items` and `paginate items` -> ["paginate", "items"]."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", keyword)
    return words(spaced)


def _close(part: str, token: str) -> bool:
    if part == token:
        return True
    if (
        len(part) >= STEM_CHARS
        and len(token) >= STEM_CHARS
        and part[:STEM_CHARS] == token[:STEM_CHARS]
    ):
        return True
    return difflib.SequenceMatcher(None, part, token).ratio() >= FUZZY_RATIO


def mentions(answer: str, fact: Fact) -> bool:
    tokens = words(answer)
    joined = "".join(tokens)
    for keyword in fact.keywords:
        parts = _parts(keyword)
        if not parts:
            continue
        if "".join(parts) in joined and len("".join(parts)) >= 4:
            return True
        if all(any(_close(p, t) for t in tokens) for p in parts):
            return True
    return False
