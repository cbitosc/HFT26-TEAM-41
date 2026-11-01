import pytest


@pytest.fixture
def twenty_five(add_expense):
    # Amounts 100..2500 on distinct days, so every expense is identifiable.
    for i in range(1, 26):
        add_expense(amount_cents=i * 100, date=f"2026-01-{i:02d}")


def get_page(client, alice, **params):
    response = client.get("/expenses", params=params, headers=alice)
    assert response.status_code == 200, response.text
    return response.json()


def test_first_page_reports_total_and_has_next(client, alice, twenty_five):
    body = get_page(client, alice, page=1, page_size=10)

    assert len(body["items"]) == 10
    assert (body["page"], body["page_size"], body["total"], body["has_next"]) == (1, 10, 25, True)


def test_last_page_is_partial_and_has_no_next(client, alice, twenty_five):
    body = get_page(client, alice, page=3, page_size=10, sort="amount")

    assert [item["amount_cents"] for item in body["items"]] == [2100, 2200, 2300, 2400, 2500]
    assert body["has_next"] is False


def test_page_past_the_end_is_empty_but_keeps_total(client, alice, twenty_five):
    body = get_page(client, alice, page=4, page_size=10)

    assert body["items"] == []
    assert (body["total"], body["has_next"]) == (25, False)


def test_full_last_page_has_no_next(client, alice, twenty_five):
    body = get_page(client, alice, page=5, page_size=5)

    assert len(body["items"]) == 5
    assert body["has_next"] is False


def test_pages_do_not_overlap(client, alice, twenty_five):
    first = get_page(client, alice, page=1, page_size=10)["items"]
    second = get_page(client, alice, page=2, page_size=10)["items"]

    assert not {item["id"] for item in first} & {item["id"] for item in second}


def test_no_expenses_gives_an_empty_first_page(client, alice):
    body = get_page(client, alice)

    assert body == {"items": [], "page": 1, "page_size": 20, "total": 0, "has_next": False}


@pytest.mark.parametrize(("page_size", "status"), [(0, 422), (1, 200), (100, 200), (101, 422)])
def test_page_size_limits(client, alice, page_size, status):
    response = client.get("/expenses", params={"page_size": page_size}, headers=alice)

    assert response.status_code == status


def test_page_must_be_at_least_one(client, alice):
    assert client.get("/expenses", params={"page": 0}, headers=alice).status_code == 422
