"""`make seed-demo`: build and validate the two P1.3 tasks, run the validation gate on them
(backend/gate; both must pass, no LLM calls), store an assessment for the portfolio fixture
with the certified specs, start its session and print the session URL.

Starting the session starts its 60-minute timer; run this again for a fresh one.

`--tier adept` (F2, for the hint assistant): the domain task is the seed's reporting
feature removed (builder.remove_feature) and enriched (builder.enrich: one generator call,
cached), the DSA task is the same demo problem; the assessment is Adept, so the session
has the assistant. `make e2e` uses the default Novice demo.
"""

import argparse
import json
import os

from app.assessments import create_assessment, get_or_start_session
from app.db import SessionLocal
from builder.manual import EXPENSES_SEED, build_dsa_task, build_pagination_task
from builder.seeds import REPO_ROOT
from gate import certify, rules_profile

PORTFOLIO = REPO_ROOT / "contracts" / "fixtures" / "portfolio.valid.json"


ADEPT_CONCEPT = "reporting"


def adept_domain_spec(portfolio: dict) -> dict:
    from builder.enrich import enrich
    from builder.remove_feature import remove_feature
    from profiler.profile import build_profile

    removal = remove_feature(EXPENSES_SEED, ADEPT_CONCEPT)
    projects = [p["name"] for p in portfolio.get("projects", []) if p.get("name")]
    enriched = enrich(removal.built.spec, build_profile(portfolio).model_dump(), projects)
    print(
        f"{enriched.spec['task_id']}: statement from {enriched.statement_source}, "
        f"renames {enriched.renames or '{}'} ({enriched.rename_status})"
    )
    return enriched.spec


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tier", choices=["novice", "adept"], default="novice")
    tier = parser.parse_args(argv).tier
    portfolio = json.loads(PORTFOLIO.read_text())
    if tier == "adept":
        tasks = [build_dsa_task()]
        domain_specs = [adept_domain_spec(portfolio)]
    else:
        tasks = [build_pagination_task(), build_dsa_task()]
        domain_specs = []
    for task in tasks:
        v = task.validation
        starter, reference = v["starter"], v["reference"]
        print(
            f"{v['task_id']}: starter visible {starter['visible']}, hidden {starter['hidden']} "
            f"(fails a visible test: {v['starter_fails_visible']}); "
            f"reference visible {reference['visible']}, hidden {reference['hidden']} "
            f"(passes everything: {v['reference_passes_all']})"
        )
    profile = rules_profile(portfolio)
    specs = []
    for draft in [*domain_specs, *(task.spec for task in tasks)]:
        spec, reasons = certify(draft, profile)
        if reasons:
            raise SystemExit(f"{draft['task_id']} failed the gate: {json.dumps(reasons)}")
        print(f"{spec['task_id']}: gate passed, certificate {json.dumps(spec['certificate'])}")
        specs.append(spec)
    with SessionLocal() as db:
        assessment = create_assessment(db, portfolio, tier, specs)
        db.commit()
        session, _ = get_or_start_session(db, assessment.id)
    frontend = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    print(f"assessment {assessment.id}")
    print(
        f"session URL: {frontend}/session/{session.id}  (deadline {session.deadline_at:%H:%M} UTC)"
    )


if __name__ == "__main__":
    main()
