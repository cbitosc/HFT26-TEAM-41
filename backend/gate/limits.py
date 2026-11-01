"""Every limit the validation gate applies, in one place."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScopeLimit:
    min_files: int
    max_files: int | None  # None: no upper bound
    max_changed_lines: int | None  # None: no upper bound
    needs_perf: bool


# Files and lines the reference changes relative to the starter, per tier.
SCOPE = {
    "novice": ScopeLimit(min_files=1, max_files=1, max_changed_lines=10, needs_perf=False),
    "adept": ScopeLimit(min_files=2, max_files=3, max_changed_lines=None, needs_perf=False),
    "master": ScopeLimit(min_files=2, max_files=None, max_changed_lines=None, needs_perf=True),
}

# The reference runs this many times; any difference between runs means it is flaky.
REFERENCE_RUNS = 3

# Tiers whose starter must fail at least one visible AND one hidden test.
FAIL_BOTH_SPLITS = {"novice", "adept"}

# DSA: every trivial stub must fail at least this share of the cases.
STUB_MIN_FAIL_RATE = 0.9

# Statement leak check (gate/leak.py): a changed reference line is checked only if it has
# at least this many tokens and one of them is an operator or punctuation (so prose like
# "return total" never counts as a leak).
LEAK_MIN_LINE_TOKENS = 3
# A single edit counts as a fix fragment on its own only with this many characters.
LEAK_MIN_EDIT_CHARS = 3
# DSA original names shorter than this are not checked (s, n, k say nothing).
LEAK_MIN_NAME_CHARS = 3
# LLM-written statements (P2.5 enrichment) longer than this are rejected like a leak.
STATEMENT_MAX_WORDS = 200

# Mutation testing (optional): sandbox timeout for the whole mutmut run.
MUTATION_TIMEOUT_S = 600
