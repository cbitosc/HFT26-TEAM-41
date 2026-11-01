"""`make gate TASK=<task_id> [MUTATION=1]`: run the gate on the most recently stored task with
that id and print its certificate (exit 0) or the reasons it was rejected (exit 1).

Profile: the assessment's stored one, else built from its portfolio by the profiler's rules
(its LLM fallback is disabled here, so the gate never calls an LLM). Runs in the worker.
"""

import argparse
import json
import sys
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Assessment, Task
from gate import check, rules_profile


def load_task(task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """(spec, profile) of the newest stored task with this id."""
    with SessionLocal() as db:
        row = db.execute(
            select(Task, Assessment)
            .join(Assessment, Task.assessment_id == Assessment.id)
            .where(Task.task_id == task_id)
            .order_by(Assessment.created_at.desc())
            .limit(1)
        ).first()
    if row is None:
        raise SystemExit(f"no stored task {task_id!r}")
    task, assessment = row
    profile = assessment.profile or rules_profile(assessment.portfolio).model_dump(mode="json")
    return task.spec, profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m gate")
    parser.add_argument("task_id")
    parser.add_argument("--mutation", action="store_true", help="also run mutmut (1-3 min)")
    args = parser.parse_args(argv)
    spec, profile = load_task(args.task_id)
    report = check(spec, profile, mutation=args.mutation)
    if report.reasons:
        print(f"{args.task_id}: REJECTED")
        print(json.dumps(report.reasons, indent=2))
        return 1
    print(f"{args.task_id}: ACCEPTED")
    print(json.dumps({"certificate": report.certificate.model_dump(mode="json")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
