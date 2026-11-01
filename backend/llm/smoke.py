"""Send one small structured request per slot and report latency and token counts.

Uses real Featherless credits on a cache miss. Run: python -m llm.smoke (or `make llm-smoke`).
"""

import logging
import sys

from pydantic import BaseModel

from llm.client import default_client, summarize_error
from llm.config import SLOTS


class StackInfo(BaseModel):
    language: str
    framework: str


MESSAGES = [
    {
        "role": "user",
        "content": 'Extract the programming language and framework from: "a REST API in FastAPI"',
    }
]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    client = default_client()
    failures = 0
    for slot in SLOTS:
        try:
            result, info = client.structured(slot, MESSAGES, StackInfo)
        except Exception as exc:
            failures += 1
            print(f"[{slot}] FAILED: {summarize_error(exc)}")
            continue
        print(
            f"[{slot}] model={info.model} latency={info.latency_ms}ms cache_hit={info.cache_hit} "
            f"prompt_tokens={info.prompt_tokens} completion_tokens={info.completion_tokens} "
            f"cost=${info.cost_usd:.6f} result={result.model_dump_json()}"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
