"""The 4-sentence recruiter summary: one generator call over the computed numbers only.

The model gets the report's numbers (scores, rates, times, efficiency parts, claim verdicts,
integrity counts), never code, tests, statements or the reference. Cached by input hash in
backend/llm, so the same report gives the same summary without a second call. Shown as
"AI summary, not scored"; it never changes a number (CLAUDE.md rule 1).
"""

import json
import re
from collections.abc import Callable
from typing import Any

from llm import complete_text
from report.build import ReportDetails

SUMMARY_MAX_TOKENS = 300
SUMMARY_TEMPERATURE = 0.2
SENTENCES = 4
LABEL = "AI summary, not scored"

SYSTEM_PROMPT = """\
You write a short summary of a coding assessment for a recruiter. Use only the numbers you
are given; do not invent facts, guess at causes or give a hiring recommendation. Write
exactly 4 plain sentences, no lists or headings: overall result and band; how each task
went; how the candidate used the AI assistant (if efficiency is given); which portfolio
claims the tasks verified, and every integrity count above zero (say they are not part of
the score; never call them "no concerns" when any count is above zero)."""


def numbers(details: ReportDetails) -> dict[str, Any]:
    b = details.breakdown
    tasks = [
        {
            "kind": t["kind"],
            "correctness": t["correctness"],
            "visible_passed": f"{t['visible']['passed']}/{t['visible']['total']}",
            "hidden_passed": f"{t['hidden']['passed']}/{t['hidden']['total']}",
            "minutes": None if t["time_ms"] is None else round(t["time_ms"] / 60_000, 1),
            "runs": t["runs"],
        }
        for t in b["tasks"]
    ]
    claims: dict[str, list[str]] = {}
    for claim in details.claims:
        claims.setdefault(claim.verdict, []).append(claim.claim)
    out: dict[str, Any] = {
        "tier": details.tier,
        "final_score": b["final_score"],
        "band": b["band"],
        "mean_correctness": b["mean_correctness"],
        "tasks": tasks,
        "claims_by_verdict": claims,
        "integrity_not_scored": {
            "pastes": len(details.integrity.pastes),
            "large_pastes": sum(p.large for p in details.integrity.pastes),
            "pastes_soon_after_a_hint": sum(p.after_hint for p in details.integrity.pastes),
            "tab_blurs": details.integrity.blurs,
            "suspicious_code_flags": len(details.integrity.flags),
            "extraction_attempts": details.integrity.extraction_attempts,
        },
    }
    if details.efficiency is not None:
        e = details.efficiency
        out["ai_efficiency"] = {
            "value": e.value,
            "hints": e.hints,
            **{p.name: p.value for p in e.parts},
        }
    return out


def first_sentences(text: str, count: int = SENTENCES) -> str:
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return " ".join(p for p in parts[:count] if p)


def summary(details: ReportDetails, llm: Callable[..., str] | None = None) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(numbers(details), indent=1, sort_keys=True)},
    ]
    text = (llm or complete_text)(
        "generator", messages, temperature=SUMMARY_TEMPERATURE, max_tokens=SUMMARY_MAX_TOKENS
    )
    return first_sentences(text)
