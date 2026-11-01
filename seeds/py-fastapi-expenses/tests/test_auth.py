def test_missing_token_is_rejected(client):
    response = client.get("/expenses")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_unknown_token_is_rejected(client):
    response = client.get("/expenses", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_non_bearer_scheme_is_rejected(client):
    response = client.get("/expenses", headers={"Authorization": "Basic YWxpY2U6c2VjcmV0"})

    assert response.status_code == 401


def test_writes_and_reports_require_auth(client):
    body = {"amount_cents": 100, "category": "food", "date": "2026-03-01"}

    assert client.post("/expenses", json=body).status_code == 401
    assert client.get("/reports/monthly?year=2026&month=3").status_code == 401


def test_users_only_see_their_own_expenses(client, add_expense, alice, bob):
    add_expense(description="alice lunch", headers=alice)
    add_expense(description="bob taxi", category="transport", headers=bob)

    alice_items = client.get("/expenses", headers=alice).json()["items"]
    bob_items = client.get("/expenses", headers=bob).json()["items"]

    assert [item["description"] for item in alice_items] == ["alice lunch"]
    assert [item["description"] for item in bob_items] == ["bob taxi"]
