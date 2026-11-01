import pytest

VALID = {"amount_cents": 1250, "category": "food", "date": "2026-03-10", "description": "lunch"}


def post(client, alice, **changes):
    return client.post("/expenses", json={**VALID, **changes}, headers=alice)


def test_valid_expense_is_created(client, alice):
    response = post(client, alice)

    assert response.status_code == 201
    body = response.json()
    assert body == {**VALID, "id": body["id"]}


@pytest.mark.parametrize("amount", [0, -500])
def test_amount_must_be_positive(client, alice, amount):
    assert post(client, alice, amount_cents=amount).status_code == 422


@pytest.mark.parametrize("amount", [12.5, "1250", True])
def test_amount_must_be_integer_cents(client, alice, amount):
    assert post(client, alice, amount_cents=amount).status_code == 422


def test_unknown_category_is_rejected(client, alice):
    assert post(client, alice, category="yachts").status_code == 422


def test_impossible_calendar_date_is_rejected(client, alice):
    response = post(client, alice, date="2026-02-30")

    assert response.status_code == 422
    assert "not a valid calendar date" in response.text


@pytest.mark.parametrize("date", ["10/03/2026", "2026-3-10", "2026-03-10T09:00:00", "1773100800"])
def test_non_iso_date_is_rejected(client, alice, date):
    assert post(client, alice, date=date).status_code == 422


def test_unexpected_field_is_rejected(client, alice):
    assert post(client, alice, user_id=2).status_code == 422


def test_invalid_date_in_query_is_rejected(client, alice):
    response = client.get("/expenses?date_from=yesterday", headers=alice)

    assert response.status_code == 422
