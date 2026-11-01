"""Build one DSA bank task for a portfolio and print it: python -m builder.dsa_demo FILE [TIER].

Profile (rules) -> select_problem -> rewrite (one real generator call on a cache miss) ->
validation in the sandbox. Run in the worker. The spec printed omits the cases.
"""

import json
import logging
import sys
from pathlib import Path

from builder.dsa_bank import build_dsa_task, select_problem
from profiler.profile import build_profile

SEED = 20261031


def main(args: list[str]) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    if not args:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    portfolio = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    profile = build_profile(portfolio)
    tier = args[1] if len(args) > 1 else profile.suggested_tier
    selection = select_problem(profile, tier, SEED)
    projects = [p["name"] for p in portfolio.get("projects", [])]
    built = build_dsa_task(
        selection.problem, profile.runtime, selection.tier, profile.domain, projects
    )
    print(f"domain {profile.domain}, runtime {profile.runtime}, tier {tier}")
    print(f"selection: {selection.reason}")
    print(f"validation: {json.dumps(built.validation)}")
    print(f"names: {json.dumps(built.spec['dsa_names'])}")
    print("\n" + built.spec["statement_md"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
