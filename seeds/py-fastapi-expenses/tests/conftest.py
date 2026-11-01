from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app

ALICE = {"Authorization": "Bearer alice-token"}
BOB = {"Authorization": "Bearer bob-token"}


@pytest.fixture
def app() -> FastAPI:
    # A fresh app per test: its own in-memory database and report cache.
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def alice() -> dict[str, str]:
    return ALICE


@pytest.fixture
def bob() -> dict[str, str]:
    return BOB


@pytest.fixture
def add_expense(client: TestClient) -> Callable[..., dict]:
    """Create an expense through the API and return the response body."""

    def add(
        amount_cents: int = 1000,
        category: str = "food",
        date: str = "2026-03-10",
        description: str = "",
        headers: dict[str, str] = ALICE,
    ) -> dict:
        body = {
            "amount_cents": amount_cents,
            "category": category,
            "date": date,
            "description": description,
        }
        response = client.post("/expenses", json=body, headers=headers)
        assert response.status_code == 201, response.text
        return response.json()

    return add
