"""Create an assessment from the contract fixtures and print its id (dev and curl testing).

Uses contracts/fixtures/portfolio.valid.json and the two valid task_spec fixtures.
P1.3's `make seed-demo` replaces this with a real seed-built task.
"""

import json
from pathlib import Path

from app.assessments import create_assessment
from app.db import SessionLocal

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def main() -> None:
    specs = [load("task_spec.valid.domain.json"), load("task_spec.valid.dsa.json")]
    with SessionLocal() as db:
        assessment = create_assessment(db, load("portfolio.valid.json"), "master", specs)
        db.commit()
        print(assessment.id)


if __name__ == "__main__":
    main()
