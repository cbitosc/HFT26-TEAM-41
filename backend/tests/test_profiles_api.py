"""POST /profiles: profile a portfolio and store it on a new assessment."""

import uuid

from app.models import Assessment
from profiler import profile as profiler
from tests.api_support import fixture, portfolio


def test_profile_is_stored_on_a_new_assessment(db, http, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(profiler, "complete_structured", lambda *a, **k: calls.append(a))

    response = http.post("/profiles", json={"portfolio": portfolio()})

    assert response.status_code == 201
    body = response.json()
    assert body["profile"] == fixture("profile.valid.json")
    assessment = db.get(Assessment, uuid.UUID(body["assessment_id"]))
    assert (assessment.status, assessment.tier) == ("profiled", "master")
    assert assessment.profile == body["profile"]
    assert assessment.portfolio == portfolio()  # stored exactly as sent
    assert calls == []  # the rules were enough


def test_invalid_portfolio_is_422(http) -> None:
    doc = portfolio()
    del doc["assessment"]

    response = http.post("/profiles", json={"portfolio": doc})

    assert response.status_code == 422
    assert "assessment" in response.text
