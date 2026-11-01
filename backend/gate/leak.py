"""Statement leak checks. The one place that decides whether a statement gives the fix away.

Used by the validation gate and by LLM enrichment (builder/enrich.py, P2.5), so a statement
is judged the same way when it is written and when it is certified.

Domain tasks: a statement leaks if it contains a changed line from the reference side of
the starter-vs-reference diff, or the exact operator/value that fixes a replaced line.
DSA tasks: a statement leaks if it names the bank's original function or parameters.
Matching is on tokens, so whitespace and Markdown backticks don't hide a leak.
LLM-written statements must also stay within STATEMENT_MAX_WORDS (statement_problems:
what enrichment rejects, retries once and then replaces with a template).
"""

import difflib
import re

from contracts_gen.task_spec import DsaNames
from gate.diff import diff
from gate.limits import (
    LEAK_MIN_EDIT_CHARS,
    LEAK_MIN_LINE_TOKENS,
    LEAK_MIN_NAME_CHARS,
    STATEMENT_MAX_WORDS,
)

_TOKEN = re.compile(r"\w+|==|!=|<=|>=|\*\*|//|->|\+=|-=|[^\w\s]")
# Any quote is the same quote; smart quotes count as plain ones.
_QUOTES = str.maketrans({"'": '"', "\u2018": '"', "\u2019": '"', "\u201c": '"', "\u201d": '"'})


def tokens(text: str) -> list[str]:
    """Code tokens; quote style is ignored and Markdown backticks are dropped."""
    return [t for t in _TOKEN.findall(text.translate(_QUOTES)) if t != "`"]


def _contains(haystack: list[str], needle: list[str]) -> bool:
    n = len(needle)
    return n > 0 and any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def _has_operator(run: list[str]) -> bool:
    return any(not t[0].isalnum() and t != "_" for t in run)


def _code_like(line: list[str]) -> bool:
    return len(line) >= LEAK_MIN_LINE_TOKENS and _has_operator(line)


def _fix_like(fragment: list[str]) -> bool:
    """An operator or a number in it: `page - 1`, `a <= b`, `return 0` (not `return total`)."""
    return _has_operator(fragment) or any(t[0].isdigit() for t in fragment)


def fix_fragments(starter_line: str, reference_line: str) -> list[list[str]]:
    """Token runs that give away how `starter_line` becomes `reference_line`.

    On the reference side: each edit alone (if it has 3+ characters) and with one token of
    context on each side; the span from the first edit to the last (if it has 2+ tokens,
    e.g. `(page - 1)`), that span with one token of context on each side, and with two
    tokens of context on the left (`page - 1` for a `2` -> `1` fix). Only runs with an
    operator or a number count. Empty when the fix only deletes tokens.
    """
    before, after = tokens(starter_line), tokens(reference_line)
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    edits = [(j1, j2) for op, _, _, j1, j2 in matcher.get_opcodes() if op != "equal" and j2 > j1]
    if not edits:
        return []
    runs = [after[j1:j2] for j1, j2 in edits if len("".join(after[j1:j2])) >= LEAK_MIN_EDIT_CHARS]
    runs += [after[max(0, j1 - 1) : j2 + 1] for j1, j2 in edits]
    start, end = edits[0][0], edits[-1][1]
    if end - start >= 2:
        runs.append(after[start:end])
    runs.append(after[max(0, start - 1) : end + 1])
    runs.append(after[max(0, start - 2) : end])
    unique = {tuple(run): run for run in runs if _fix_like(run)}
    return list(unique.values())


def fix_evidence(
    reference_files: dict[str, str], starter_files: dict[str, str]
) -> tuple[list[str], list[str]]:
    """(reference-side changed lines, fixing fragments) for the files in `reference_files`."""
    changes = diff({p: starter_files.get(p, "") for p in reference_files}, reference_files)
    lines = [
        line.strip() for line in dict.fromkeys(changes.reference_lines) if _code_like(tokens(line))
    ]
    fragments = [
        " ".join(run) for before, after in changes.replaced for run in fix_fragments(before, after)
    ]
    return lines, list(dict.fromkeys(fragments))


def leaks(text: str, reference_lines: list[str], fragments: list[str]) -> list[str]:
    """Why `text` gives the fix away; empty when it doesn't."""
    told = tokens(text)
    reasons = [
        f"contains reference line `{line}`"
        for line in reference_lines
        if _contains(told, tokens(line))
    ]
    reasons += [
        f"contains the fix `{fragment}`"
        for fragment in fragments
        if _contains(told, tokens(fragment))
    ]
    return reasons


def domain_leaks(
    statement: str, starter_files: dict[str, str], reference_files: dict[str, str]
) -> list[str]:
    """leaks() for a statement, given the task's starter and reference files."""
    return leaks(statement, *fix_evidence(reference_files, starter_files))


def too_long(statement: str, max_words: int = STATEMENT_MAX_WORDS) -> bool:
    return len(statement.split()) > max_words


def statement_problems(text: str, reference_lines: list[str], fragments: list[str]) -> list[str]:
    """Why an LLM-written statement is rejected (P2.5): leaks(), then the word limit.

    The gate itself checks leaks only; the word limit applies to generated statements.
    """
    problems = leaks(text, reference_lines, fragments)
    if too_long(text):
        problems.append(f"longer than {STATEMENT_MAX_WORDS} words")
    return problems


def name_leaks(statement: str, names: DsaNames | None) -> list[str]:
    """Original (bank) names that appear in the statement as whole words."""
    if names is None:
        return []
    mappings = [names.function, *names.parameters]
    return [
        m.original
        for m in mappings
        if m.original != m.renamed
        and len(m.original) >= LEAK_MIN_NAME_CHARS
        and re.search(rf"(?<![A-Za-z0-9_]){re.escape(m.original)}(?![A-Za-z0-9_])", statement)
    ]
