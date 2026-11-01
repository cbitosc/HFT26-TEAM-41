"""Plain-code checks on everything the interviewer says, generated or not.

A question or reply that touches a protected attribute, contains code, or talks about
solutions, reference code or hidden tests is dropped and replaced with scripted text.
"""

import re

MAX_REPLY_WORDS = 60

_PROTECTED = re.compile(
    r"\b(age|aged|how old|birth ?(day|date|year)|religio\w*|church|mosque|temple|faith|"
    r"pray\w*|married|marital|spouse|husband|wife|children|kids|pregnan\w*|"
    r"family|families|parents?|nationality|citizen\w*|immigra\w*|ethnic\w*|race(?!\s+conditions?)|"
    r"racial|caste|skin|gender|sex|sexual\w*|orientation|health(?![\s-]*checks?)|illness|disab\w*|"
    r"medical|medication|diagnos\w*|politic\w*|union member\w*|accent)\b",
    re.IGNORECASE,
)
_LEAK = re.compile(
    r"\b(hidden|secret)\s+tests?\b|\breference\s+(solution|code|implementation)\b|"
    r"\bthe\s+(correct|right|full)\s+(solution|answer|code)\s+(is|was)\b",
    re.IGNORECASE,
)
_CODE = re.compile(
    r"```|`[^`]*[(){};=][^`]*`|^\s*(def|class|return|import|const|let|function)\b|[{};]\s*$",
    re.MULTILINE,
)


def protected(text: str) -> bool:
    return bool(_PROTECTED.search(text))


def problem(text: str) -> str | None:
    """Why `text` may not be said, or None when it is fine."""
    if not text.strip():
        return "empty"
    if protected(text):
        return "protected attribute"
    if _LEAK.search(text):
        return "mentions solutions or hidden tests"
    if _CODE.search(text):
        return "contains code"
    if len(text.split()) > MAX_REPLY_WORDS:
        return "too long"
    return None
