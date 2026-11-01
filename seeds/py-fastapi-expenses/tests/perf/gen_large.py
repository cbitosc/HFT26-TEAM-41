"""Deterministic large inputs for the perf tests: 50,000 expenses over 2024-2026.

Alice (user 1) owns four in five of them, Bob (user 2) the rest. The same seed always
gives the same rows, so timings are comparable across runs.
"""

import datetime as dt
import random
import time
from collections.abc import Callable

from sqlalchemy import insert
from sqlalchemy.orm import Session, sessionmaker

from app.models import Category, Expense

SIZE = 50_000
ALICE, BOB = 1, 2
FIRST_DAY = dt.date(2024, 1, 1)
DAYS = 3 * 365 + 1
REPEATS = 3
SLOW_S = 1.0
"""A repetition slower than this is already far over any budget: stop repeating."""


def expenses(size: int = SIZE, seed: int = 2026) -> list[dict]:
    """Rows for the expenses table, ready for a bulk insert."""
    rng = random.Random(seed)
    categories = [category.value for category in Category]
    return [
        {
            "user_id": BOB if i % 5 == 0 else ALICE,
            "amount_cents": rng.randint(100, 50_000),
            "category": rng.choice(categories),
            "spent_on": FIRST_DAY + dt.timedelta(days=rng.randrange(DAYS)),
            "description": f"item {rng.randrange(1_000)}",
        }
        for i in range(size)
    ]


def load(session_factory: sessionmaker[Session], rows: list[dict]) -> None:
    with session_factory.begin() as session:
        session.execute(insert(Expense), rows)


def import_batch(rows: list[dict], seed: int = 7) -> tuple[list[dict], int]:
    """(4,000 import items for Alice over the whole period, how many of them are new).

    1,600 copy stored expenses, 2,000 are new, 400 repeat earlier items of the batch.
    """
    rng = random.Random(seed)
    stored = [r for r in rows if r["user_id"] == ALICE]
    items = [
        {k: r[k] for k in ("amount_cents", "category", "description")} | {"date": r["spent_on"]}
        for r in rng.sample(stored, 1_600)
    ]
    items += [
        {
            "amount_cents": rng.randint(100, 50_000),
            "category": rng.choice([category.value for category in Category]),
            "date": FIRST_DAY + dt.timedelta(days=rng.randrange(DAYS)),
            "description": f"import {n}",
        }
        for n in range(2_000)
    ]
    items += [rng.choice(items) for _ in range(400)]
    rng.shuffle(items)
    return items, 2_000


def best_ms(run: Callable[[], object], reset: Callable[[], None] = lambda: None) -> float:
    """Best of REPEATS timed calls of `run`, in ms; `reset` restores the state after each."""
    best = float("inf")
    for _ in range(REPEATS):
        start = time.perf_counter()
        run()
        elapsed = time.perf_counter() - start
        reset()
        best = min(best, elapsed)
        if elapsed > SLOW_S:
            break
    return round(best * 1000, 3)
