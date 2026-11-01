"""Plain-code guards around the hint model: nothing here calls a model.

Input: extraction_reason() flags requests for the solution, the reference or the hidden
tests, and attempts to override the assistant's instructions; a flagged request gets a
refusal and is never sent to the model.
Output: code in a reply is capped at MAX_CODE_LINES lines, and reply code that copydetect
finds too similar to the reference side of the fix is replaced by a level-1 nudge.
"""

import io
import logging
import re

from copydetect import CodeFingerprint, compare_files

MAX_CODE_LINES = 5
# Share of the reply's code fingerprint that may overlap the reference fix.
MAX_SIMILARITY = 0.5
# copydetect fingerprints k-grams of the filtered code (names become V/F/O, strings S).
# Hints are a few lines, so k is smaller than copydetect's default of 25.
FINGERPRINT_K = 10
FINGERPRINT_WINDOW = 3
LANGUAGES = {"python311": "python", "node20": "javascript"}

_EXTRACTION = [
    (
        "asks for the solution",
        r"\b(give|show|write|send|paste|provide|print|tell)\b(\s+\w+){0,3}\s+"
        r"(full|complete|entire|whole|final|correct|working|exact)\s+"
        r"(solution|answer|code|implementation|function|fix)",
    ),
    (
        "asks for the solution",
        r"\b(solve|finish|complete|implement|fix|write|do)\b\s+"
        r"(it|this|that|everything|the\s+\w+(\s+\w+)?)\s+for\s+me\b",
    ),
    (
        "asks for the solution",
        r"\bjust\s+(give|tell|show|write)\b(\s+\w+){0,2}\s+(answer|code|solution)",
    ),
    (
        "asks for the reference or hidden tests",
        r"\b(reference|hidden|official|model)\s+(solution|tests?|implementation|answer|code)",
    ),
    (
        "tries to override the instructions",
        r"\b(ignore|disregard|forget|override)\b(\s+\w+){0,3}\s+(instructions|rules|prompt|guidelines)",
    ),
    ("tries to override the instructions", r"\b(system|developer)\s+(prompt|message|instructions)"),
    (
        "tries to override the instructions",
        r"\b(you are now|pretend (to be|you are)|jailbreak|DAN mode)\b",
    ),
]
_EXTRACTION_RE = [(reason, re.compile(pattern, re.IGNORECASE)) for reason, pattern in _EXTRACTION]
_FENCE = re.compile(r"```[^\n]*\n(.*?)(?:```|$)", re.DOTALL)
_INLINE = re.compile(r"`([^`\n]+)`")

logging.getLogger("copydetect").setLevel(logging.ERROR)


def extraction_reason(question: str) -> str | None:
    """Why the request looks like an extraction attempt, or None."""
    for reason, pattern in _EXTRACTION_RE:
        if pattern.search(question):
            return reason
    return None


def code_of(reply: str) -> str:
    """The code in a reply: fenced blocks, then inline `code` spans, one per line."""
    blocks = [m.group(1) for m in _FENCE.finditer(reply)]
    inline = [m.group(1) for m in _INLINE.finditer(_FENCE.sub("", reply))]
    return "\n".join([*blocks, *inline]).strip()


def cap_code_lines(reply: str, limit: int = MAX_CODE_LINES) -> tuple[str, bool]:
    """Keep at most `limit` non-blank lines of fenced code in total; (reply, trimmed)."""
    budget = limit
    trimmed = False

    def keep(match: re.Match[str]) -> str:
        nonlocal budget, trimmed
        header = match.group(0).split("\n", 1)[0]
        kept = []
        for line in match.group(1).splitlines():
            if not line.strip():
                kept.append(line)
                continue
            if budget == 0:
                trimmed = True
                continue
            budget -= 1
            kept.append(line)
        body = "\n".join(kept).rstrip("\n")
        return f"{header}\n{body}\n```" if body.strip() else ""

    capped = _FENCE.sub(keep, reply)
    if trimmed:
        capped = capped.rstrip() + f"\n\n(Code trimmed to {limit} lines.)"
    return capped, trimmed


def _fingerprint(code: str, language: str) -> CodeFingerprint:
    return CodeFingerprint(
        f"snippet.{language}",
        FINGERPRINT_K,
        FINGERPRINT_WINDOW,
        language=language,
        fp=io.StringIO(code),
    )


def similarity(code: str, code_language: str, reference: str, reference_language: str) -> float:
    """Share of `code`'s fingerprint found in `reference` (0 when either is too short)."""
    if not code.strip() or not reference.strip():
        return 0.0
    reply_fp = _fingerprint(code, code_language)
    reference_fp = _fingerprint(reference, reference_language)
    if not len(reply_fp.hashes) or not len(reference_fp.hashes):
        return 0.0
    _, (share, _), _ = compare_files(reply_fp, reference_fp)
    return round(float(min(1.0, share)), 4)


def mentions(reply: str, names: list[str]) -> list[str]:
    """The names (functions, files) the reply mentions as whole words."""
    return sorted(
        {
            name
            for name in names
            if name and re.search(rf"(?<![\w/.]){re.escape(name)}(?![\w/])", reply)
        }
    )
