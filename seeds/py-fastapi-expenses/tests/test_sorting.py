import pytest


@pytest.fixture
def three(add_expense):
    add_expense(description="mid", amount_cents=500, date="2026-03-02")
    add_expense(description="old", amount_cents=900, date="2026-03-01")
    add_expense(description="new", amount_cents=100, date="2026-03-03")


def descriptions(client, alice, **params):
    response = client.get("/expenses", params=params, headers=alice)
    assert response.status_code == 200, response.text
    return [item["description"] for item in response.json()["items"]]


def test_default_sort_is_newest_first(client, alice, three):
    assert descriptions(client, alice) == ["new", "mid", "old"]


def test_sort_by_date_ascending(client, alice, three):
    assert descriptions(client, alice, sort="date") == ["old", "mid", "new"]


def test_sort_by_amount_ascending(client, alice, three):
    assert descriptions(client, alice, sort="amount") == ["new", "mid", "old"]


def test_sort_by_amount_descending(client, alice, three):
    assert descriptions(client, alice, sort="-amount") == ["old", "mid", "new"]


def test_ties_break_on_creation_order(client, alice, add_expense):
    for name in ("first", "second", "third"):
        add_expense(description=name, amount_cents=700, date="2026-03-05")

    assert descriptions(client, alice, sort="amount") == ["first", "second", "third"]
    assert descriptions(client, alice, sort="-amount") == ["third", "second", "first"]


def test_unknown_sort_key_is_rejected(client, alice):
    assert client.get("/expenses?sort=description", headers=alice).status_code == 422
