"""Regenerate cases.json: hand-picked inputs plus seeded random strings, answered by
reference.py. Run from this directory: `python make_cases.py`. The builder re-checks the
reference against every case in the sandbox, so a wrong answer here fails the build.
"""

import json
import random
import string
from pathlib import Path

from reference import length_of_longest_substring

SEED = 20261031
VISIBLE = ["abcabcbb", "bbbbb", "pwwkew", "", "dvdf"]
HIDDEN_FIXED = [
    " ",
    "a",
    "au",
    "abba",
    "tmmzuxt",
    "aab",
    "abcdefghijklmnopqrstuvwxyz",
    "aAbBcC",
    "a b c a",
    "1231234",
    "anviaj",
    "ohomm",
    "zzzzzzzzzza",
    "abcdeabcdefabcdefg",
]


def random_inputs(rng: random.Random) -> list[str]:
    inputs = []
    for alphabet, length in [
        ("ab", 50),
        ("abc", 200),
        (string.ascii_lowercase, 30),
        (string.ascii_lowercase, 500),
        (string.ascii_letters, 1000),
        (string.ascii_letters + string.digits, 2000),
        (string.printable[:95], 3000),
        ("xyz", 3000),
    ]:
        inputs.append("".join(rng.choice(alphabet) for _ in range(length)))
    # Long strings whose answer is the whole alphabet, placed at the end and the start.
    inputs.append("a" * 500 + string.ascii_lowercase)
    inputs.append(string.ascii_letters + "Z" * 800)
    return inputs


def main() -> None:
    rng = random.Random(SEED)
    hidden = HIDDEN_FIXED + random_inputs(rng)
    while len(hidden) < 30:
        hidden.append("".join(rng.choice("abcdef") for _ in range(rng.randint(5, 60))))
    cases = {
        "visible": [
            {"id": f"v{i}", "input": {"s": s}, "expected": length_of_longest_substring(s)}
            for i, s in enumerate(VISIBLE, start=1)
        ],
        "hidden": [
            {"id": f"h{i:02d}", "input": {"s": s}, "expected": length_of_longest_substring(s)}
            for i, s in enumerate(hidden[:30], start=1)
        ],
    }
    Path("cases.json").write_text(json.dumps(cases, indent=1) + "\n")


if __name__ == "__main__":
    main()
