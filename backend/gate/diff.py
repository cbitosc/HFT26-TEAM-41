"""The starter-vs-reference diff: which files and lines the fix changes.

Lines are compared as code: comments, blank lines and whitespace inside a line are ignored
(indentation is kept: it is code in Python), so a reworded comment or a reformatted line
doesn't count as part of the fix.
"""

import difflib
import io
import re
import tokenize
from dataclasses import dataclass

_TOKEN = re.compile(r"\w+|==|!=|<=|>=|\*\*|//|->|\+=|-=|[^\w\s]")


@dataclass(frozen=True)
class Diff:
    files: list[str]
    """Paths whose code differs, sorted."""
    changed_lines: int
    """A replaced line counts once: max(starter lines, reference lines) per changed block."""
    reference_lines: list[str]
    """Reference-side lines of the diff without comments (what the candidate has to write)."""
    replaced: list[tuple[str, str]]
    """(starter line, reference line) pairs from blocks replacing as many lines as they remove."""


def _without_comments(path: str, text: str) -> list[str]:
    """`text`'s lines with comments blanked out (Python: via tokenize; else full-line # and //)."""
    lines = text.splitlines()
    if path.endswith(".py"):
        try:
            for token in tokenize.generate_tokens(io.StringIO(text).readline):
                if token.type == tokenize.COMMENT:
                    row, col = token.start
                    lines[row - 1] = lines[row - 1][:col]
            return lines
        except (tokenize.TokenError, SyntaxError, IndexError):
            lines = text.splitlines()  # not valid Python: fall back to the line rule
    return ["" if line.lstrip().startswith(("#", "//")) else line for line in lines]


def code_lines(path: str, text: str) -> list[tuple[str, str]]:
    """(normalized, code) for every line holding code: normalized = indentation + tokens,
    code = the line without its comment."""
    result = []
    for code in _without_comments(path, text):
        if code.strip():
            indent = code[: len(code) - len(code.lstrip())]
            result.append((indent + " ".join(_TOKEN.findall(code)), code.rstrip()))
    return result


def diff(starter: dict[str, str], reference: dict[str, str]) -> Diff:
    files, changed, reference_lines, replaced = [], 0, [], []
    for path in sorted(set(starter) | set(reference)):
        before = code_lines(path, starter.get(path, ""))
        after = code_lines(path, reference.get(path, ""))
        a, b = [n for n, _ in before], [n for n, _ in after]
        if a == b:
            continue
        files.append(path)
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if op == "equal":
                continue
            changed += max(i2 - i1, j2 - j1)
            reference_lines += [o for _, o in after[j1:j2]]
            if op == "replace" and i2 - i1 == j2 - j1:
                pairs = zip(before[i1:i2], after[j1:j2], strict=True)
                replaced += [(old, new) for (_, old), (_, new) in pairs]
    return Diff(files, changed, reference_lines, replaced)
