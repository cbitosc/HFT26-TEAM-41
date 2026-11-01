"""Suspicious-code scan of a candidate's changed files.

The result is an integrity note stored on the run, shown to recruiters. It never blocks a
run and never affects the score (CLAUDE.md rule 8): every rule here has innocent uses.
"""

import ast
import re

from pydantic import BaseModel

LINE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("pytest_internals", re.compile(r"\b_pytest\b")),
    ("sys_modules", re.compile(r"\bsys\.modules\b")),
    ("os_exit", re.compile(r"\bos\._exit\s*\(")),
    ("process_exit", re.compile(r"\bprocess\.exit\s*\(")),
    (
        "builtins_patching",
        re.compile(r"\b__builtins__\b|\bbuiltins\.\w+\s*=(?!=)|setattr\(\s*builtins\b"),
    ),
    ("importlib_tricks", re.compile(r"\bimportlib\b|\b__import__\s*\(|\brequire\.cache\b")),
]
# A string literal holding an absolute path outside /workspace, on a line that writes.
OUTSIDE_PATH = re.compile(r"""['"`](/(?!workspace(?:/|['"`]))[^'"`]*)['"`]""")
WRITE_CALL = re.compile(
    r"\bopen\s*\(|\.write|writeFile|appendFile|\bPath\s*\(|\bos\.(remove|rename)"
)
EXIT_CALLS = {("sys", "exit"), (None, "exit"), (None, "quit")}
EXCERPT_CHARS = 200


class IntegrityFlag(BaseModel):
    path: str
    line: int
    rule: str
    excerpt: str


def scan(files: dict[str, str]) -> list[IntegrityFlag]:
    flags = []
    for path, content in sorted(files.items()):
        lines = content.splitlines()
        for number, text in enumerate(lines, start=1):
            for rule, pattern in LINE_RULES:
                if pattern.search(text):
                    flags.append(_flag(path, number, rule, text))
            if WRITE_CALL.search(text) and OUTSIDE_PATH.search(text):
                flags.append(_flag(path, number, "write_outside_workspace", text))
        if path.endswith(".py"):
            for number in _module_level_exits(content):
                flags.append(_flag(path, number, "module_level_exit", lines[number - 1]))
    return flags


def _flag(path: str, line: int, rule: str, text: str) -> IntegrityFlag:
    return IntegrityFlag(path=path, line=line, rule=rule, excerpt=text.strip()[:EXCERPT_CHARS])


def _module_level_exits(source: str) -> list[int]:
    """Lines of sys.exit()/exit()/quit() calls that run at import time."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [
            i
            for i, line in enumerate(source.splitlines(), 1)
            if re.match(r"(sys\.)?exit\s*\(|quit\s*\(", line)
        ]
    lines = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                name = (func.value.id, func.attr)
            elif isinstance(func, ast.Name):
                name = (None, func.id)
            else:
                continue
            if name in EXIT_CALLS:
                lines.append(node.lineno)
    return lines
