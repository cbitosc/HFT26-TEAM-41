"""Print the Profile of each portfolio file: python -m profiler FILE [FILE ...].

Uses the real LLM fallback (cached) when the rules find no domain or no concept.
"""

import json
import logging
import sys
from pathlib import Path

from profiler.profile import build_profile


def main(paths: list[str]) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    if not paths:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    for path in paths:
        profile = build_profile(json.loads(Path(path).read_text(encoding="utf-8")))
        print(f"== {Path(path).name}")
        print(profile.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
