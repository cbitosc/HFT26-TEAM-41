import pytest


def item(amount_cents=1000, category="food", date="2026-03-10", description=""):
    return {
        "amount_cents": amount_cents,
        "category": category,
        "date": date,
        "description": description,
    }


def import_items(client, headers, items):
    response = client.post("/expenses/import", json=items, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def total(client, headers):
    return client.get("/expenses", headers=headers).json()["total"]


def test_import_creates_every_new_expense(client, alice):
    items = [item(amount_cents=100 * n, description=f"n{n}") for n in range(1, 4)]

    assert import_items(client, alice, items) == {"created": 3, "skipped": 0}
    assert total(client, alice) == 3


def test_duplicates_of_stored_expenses_are_skipped(client, alice, add_expense):
    add_expense(amount_cents=500, category="food", date="2026-03-02", description="lunch")
    items = [
        item(amount_cents=500, date="2026-03-02", description="lunch"),
        item(amount_cents=500, date="2026-03-02", description="dinner"),
    ]

    assert import_items(client, alice, items) == {"created": 1, "skipped": 1}
    assert total(client, alice) == 2


def test_repeated_items_in_one_import_are_created_once(client, alice):
    items = [item(description="taxi"), item(description="taxi"), item(description="bus")]

    assert import_items(client, alice, items) == {"created": 2, "skipped": 1}


def test_another_users_expense_is_not_a_duplicate(client, alice, bob, add_expense):
    add_expense(amount_cents=700, headers=bob)

    assert import_items(client, alice, [item(amount_cents=700)]) == {"created": 1, "skipped": 0}


def test_import_invalidates_cached_reports_of_its_months(client, alice, add_expense):
    add_expense(amount_cents=500, date="2026-03-10")
    params = {"year": 2026, "month": 3}
    assert client.get("/reports/monthly", params=params, headers=alice).json()["total_cents"] == 500

    import_items(client, alice, [item(amount_cents=250, date="2026-03-11")])

    report = client.get("/reports/monthly", params=params, headers=alice).json()
    assert report["total_cents"] == 750


@pytest.mark.parametrize("items", [[], [item()] * 5_001])
def test_empty_or_oversized_import_is_rejected(client, alice, items):
    assert client.post("/expenses/import", json=items, headers=alice).status_code == 422


def test_one_invalid_item_rejects_the_whole_import(client, alice):
    response = client.post("/expenses/import", json=[item(), item(amount_cents=-1)], headers=alice)

    assert response.status_code == 422
    assert total(client, alice) == 0
