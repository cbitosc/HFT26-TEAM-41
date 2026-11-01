from app.schemas import MonthlyReport
from app.services import ReportCache


def report(client, headers, month=3):
    params = {"year": 2026, "month": month}
    response = client.get("/reports/monthly", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_repeated_report_is_served_from_cache(app, client, alice, add_expense):
    add_expense(amount_cents=500)
    cache = app.state.report_cache

    first = report(client, alice)
    second = report(client, alice)

    assert first == second
    assert (cache.misses, cache.hits) == (1, 1)


def test_new_expense_invalidates_its_month(client, alice, add_expense):
    add_expense(amount_cents=500, date="2026-03-10")
    assert report(client, alice)["total_cents"] == 500

    add_expense(amount_cents=250, date="2026-03-11")

    assert report(client, alice)["total_cents"] == 750


def test_new_expense_keeps_other_months_cached(app, client, alice, add_expense):
    add_expense(amount_cents=500, date="2026-03-10")
    report(client, alice, month=3)

    add_expense(amount_cents=999, date="2026-04-02")
    assert report(client, alice, month=3)["total_cents"] == 500

    assert app.state.report_cache.hits == 1


def test_cache_is_per_user(app, client, alice, bob, add_expense):
    add_expense(amount_cents=500, headers=alice)
    report(client, alice)

    add_expense(amount_cents=700, headers=bob)

    assert report(client, bob)["total_cents"] == 700
    assert report(client, alice)["total_cents"] == 500
    assert app.state.report_cache.hits == 1  # alice's second read; bob's first was a miss


def test_cache_evicts_least_recently_used_entry_when_full():
    cache = ReportCache(max_entries=2)
    reports = {m: MonthlyReport(year=2026, month=m, totals={}, total_cents=m) for m in (1, 2, 3)}

    cache.put((1, 2026, 1), reports[1])
    cache.put((1, 2026, 2), reports[2])
    cache.get((1, 2026, 1))  # month 1 is now the most recently used
    cache.put((1, 2026, 3), reports[3])

    assert cache.get((1, 2026, 1)) is reports[1]
    assert cache.get((1, 2026, 2)) is None
    assert cache.get((1, 2026, 3)) is reports[3]
