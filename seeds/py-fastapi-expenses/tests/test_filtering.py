import pytest


@pytest.fixture
def mixed(add_expense):
    add_expense(description="groceries", category="food", date="2026-02-28")
    add_expense(description="bus pass", category="transport", date="2026-03-01")
    add_expense(description="dinner", category="food", date="2026-03-15")
    add_expense(description="cinema", category="entertainment", date="2026-03-31")
    add_expense(description="brunch", category="food", date="2026-04-01")


def descriptions(client, alice, **params):
    response = client.get("/expenses", params={**params, "sort": "date"}, headers=alice)
    assert response.status_code == 200, response.text
    return [item["description"] for item in response.json()["items"]]


def test_filter_by_category(client, alice, mixed):
    assert descriptions(client, alice, category="food") == ["groceries", "dinner", "brunch"]


def test_date_range_includes_both_ends(client, alice, mixed):
    result = descriptions(client, alice, date_from="2026-03-01", date_to="2026-03-31")

    assert result == ["bus pass", "dinner", "cinema"]


def test_open_ended_date_range(client, alice, mixed):
    assert descriptions(client, alice, date_from="2026-03-31") == ["cinema", "brunch"]
    assert descriptions(client, alice, date_to="2026-02-28") == ["groceries"]


def test_category_and_dates_combine(client, alice, mixed):
    result = descriptions(client, alice, category="food", date_from="2026-03-01")

    assert result == ["dinner", "brunch"]


def test_filters_change_the_total(client, alice, mixed):
    body = client.get("/expenses", params={"category": "food"}, headers=alice).json()

    assert body["total"] == 3


def test_date_from_after_date_to_is_rejected(client, alice):
    response = client.get(
        "/expenses", params={"date_from": "2026-03-02", "date_to": "2026-03-01"}, headers=alice
    )

    assert response.status_code == 422
    assert "date_from must not be after date_to" in response.text


def test_unknown_category_filter_is_rejected(client, alice):
    assert client.get("/expenses?category=yachts", headers=alice).status_code == 422
