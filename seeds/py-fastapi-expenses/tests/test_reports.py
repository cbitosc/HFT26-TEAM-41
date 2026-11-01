import pytest


def report(client, headers, year=2026, month=3):
    params = {"year": year, "month": month}
    response = client.get("/reports/monthly", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_totals_per_category(client, alice, add_expense):
    add_expense(amount_cents=1200, category="food", date="2026-03-02")
    add_expense(amount_cents=800, category="food", date="2026-03-20")
    add_expense(amount_cents=4500, category="transport", date="2026-03-05")

    assert report(client, alice) == {
        "year": 2026,
        "month": 3,
        "totals": {"food": 2000, "transport": 4500},
        "total_cents": 6500,
    }


def test_month_boundaries(client, alice, add_expense):
    add_expense(amount_cents=1, date="2026-02-28")
    add_expense(amount_cents=10, date="2026-03-01")
    add_expense(amount_cents=100, date="2026-03-31")
    add_expense(amount_cents=1000, date="2026-04-01")

    assert report(client, alice)["total_cents"] == 110


def test_other_users_are_excluded(client, alice, bob, add_expense):
    add_expense(amount_cents=300, headers=alice)
    add_expense(amount_cents=999, headers=bob)

    assert report(client, alice)["total_cents"] == 300


def test_empty_month(client, alice):
    assert report(client, alice) == {"year": 2026, "month": 3, "totals": {}, "total_cents": 0}


def test_december_ends_at_new_year(client, alice, add_expense):
    add_expense(amount_cents=250, date="2026-12-31")
    add_expense(amount_cents=999, date="2027-01-01")

    assert report(client, alice, year=2026, month=12)["total_cents"] == 250


@pytest.mark.parametrize(("year", "month"), [(2026, 0), (2026, 13), (1999, 6)])
def test_out_of_range_month_or_year_is_rejected(client, alice, year, month):
    params = {"year": year, "month": month}
    response = client.get("/reports/monthly", params=params, headers=alice)

    assert response.status_code == 422


def test_year_and_month_are_required(client, alice):
    assert client.get("/reports/monthly?year=2026", headers=alice).status_code == 422
