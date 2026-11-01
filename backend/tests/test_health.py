from fastapi.testclient import TestClient


# Runs against the real Postgres and Redis from docker compose (see `make test`).
def test_health_reports_live_dependencies(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True, "redis": True}
