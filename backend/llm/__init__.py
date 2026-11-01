"""The only way this project calls Featherless (CLAUDE.md rule 6).

Code refers to model slots ("generator", "assistant", "probe", "interviewer"), never to
model IDs.
"""

from llm.budget import BudgetExceededError
from llm.client import complete_structured, complete_text, default_client, synthesize_speech
from llm.config import SLOTS, Slot

__all__ = [
    "SLOTS",
    "BudgetExceededError",
    "Slot",
    "complete_structured",
    "complete_text",
    "default_client",
    "synthesize_speech",
]
