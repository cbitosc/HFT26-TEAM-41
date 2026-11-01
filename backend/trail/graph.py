"""Function spans and a name-based call graph from Python source (ast, no execution).

A node is a top-level function or a class method, id "path::qualname" (the same form as
TaskSpec.target_symbols), plus one "path" node per file for lines outside any function.
Edges are by name: a call to `name(...)` or `obj.name(...)` links to every node whose
last name part is `name`, preferring the caller's own file when it has one. Non-Python
files (e.g. solution.js) get only their file node.
"""

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    id: str
    file: str
    name: str
    start: int
    end: int


def spans(path: str, source: str) -> list[Span] | None:
    """The file's function spans, or None when it doesn't parse (e.g. mid-edit)."""
    if not path.endswith(".py"):
        return []
    try:
        module = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    out = []
    for node in module.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            out.append(Span(f"{path}::{node.name}", path, node.name, node.lineno, node.end_lineno))
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    qualname = f"{node.name}.{item.name}"
                    out.append(
                        Span(f"{path}::{qualname}", path, qualname, item.lineno, item.end_lineno)
                    )
    return out


def node_at(file_spans: list[Span], path: str, line: int, source: str | None = None) -> str:
    """The innermost function containing `line`, else the file node.

    With `source`, blank lines right after a function (where an editor leaves the cursor
    at the end of a file or after a paste) belong to that function.
    """
    inside = [s for s in file_spans if s.start <= line <= s.end]
    if inside:
        return min(inside, key=lambda s: s.end - s.start).id
    if source is not None:
        lines = source.splitlines()
        before = [s for s in file_spans if s.end < line]
        if before:
            last = max(before, key=lambda s: s.end)
            gap = lines[last.end : line]
            starts_between = any(last.end < s.start <= line for s in file_spans)
            if not starts_between and all(not text.strip() for text in gap):
                return last.id
    return path


def _calls(function: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def call_edges(files: dict[str, str], all_spans: list[Span]) -> list[tuple[str, str]]:
    """(caller id, callee id) pairs, sorted, without self-loops."""
    by_name: dict[str, list[Span]] = {}
    for span in all_spans:
        by_name.setdefault(span.name.rsplit(".", 1)[-1], []).append(span)
    edges = set()
    for path, source in files.items():
        if not path.endswith(".py"):
            continue
        try:
            module = ast.parse(source)
        except (SyntaxError, ValueError):
            continue
        functions = []
        for node in module.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                functions.append((f"{path}::{node.name}", node))
            elif isinstance(node, ast.ClassDef):
                functions += [
                    (f"{path}::{node.name}.{item.name}", item)
                    for item in node.body
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                ]
        for caller, function in functions:
            for name in _calls(function):
                targets = by_name.get(name, [])
                local = [t for t in targets if t.file == path]
                for target in local or targets:
                    if target.id != caller:
                        edges.add((caller, target.id))
    return sorted(edges)
