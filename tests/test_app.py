from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from app.main import create_app


def make_transport(responses: list[httpx.Response]):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(calls["count"], len(responses) - 1)
        calls["count"] += 1
        return responses[index]

    return httpx.MockTransport(handler), calls


def test_sync_retries_validates_upserts_and_exports_csv(tmp_path):
    first_payload = [
        {"id": "cust-1", "name": " Alice Example ", "status": "ACTIVE"},
        {"id": "cust-2", "name": "Bob Example", "status": "pending"},
        {"id": "", "name": "Broken", "status": "active"},
        "not-an-object",
    ]
    transport, calls = make_transport(
        [
            httpx.Response(503, json={"error": "temporary"}),
            httpx.Response(200, content=json.dumps(first_payload).encode()),
        ]
    )
    app = create_app(
        db_path=tmp_path / "pilot.sqlite3",
        upstream_url="https://example.test/customers",
        upstream_transport=transport,
        retry_delay_seconds=0,
    )

    with TestClient(app) as client:
        first = client.post("/sync")
        assert first.status_code == 200
        assert first.json() == {
            "inserted": 2,
            "updated": 0,
            "unchanged": 0,
            "rejected": 2,
            "received": 4,
        }
        assert calls["count"] == 2

        records = client.get("/records")
        assert records.json() == [
            {"external_id": "cust-1", "name": "Alice Example", "status": "active"},
            {"external_id": "cust-2", "name": "Bob Example", "status": "pending"},
        ]

        second = client.post("/sync")
        assert second.json()["unchanged"] == 2

        csv_response = client.get("/records.csv")
        assert csv_response.status_code == 200
        assert "cust-1,Alice Example,active" in csv_response.text
        assert "cust-2,Bob Example,pending" in csv_response.text


def test_sync_updates_changed_record(tmp_path):
    transport, _ = make_transport(
        [
            httpx.Response(200, json=[{"id": "1", "name": "Alice", "status": "active"}]),
            httpx.Response(200, json=[{"id": "1", "name": "Alice", "status": "inactive"}]),
        ]
    )
    app = create_app(
        db_path=tmp_path / "pilot.sqlite3",
        upstream_url="https://example.test/customers",
        upstream_transport=transport,
        retry_delay_seconds=0,
    )
    with TestClient(app) as client:
        assert client.post("/sync").json()["inserted"] == 1
        result = client.post("/sync").json()
        assert result["updated"] == 1
        assert client.get("/records").json()[0]["status"] == "inactive"


def test_sync_requires_configured_upstream(tmp_path):
    app = create_app(db_path=tmp_path / "pilot.sqlite3", upstream_url=None)
    with TestClient(app) as client:
        response = client.post("/sync")
        assert response.status_code == 503
        assert response.json()["detail"] == "PILOT_UPSTREAM_URL is not configured"


def test_non_retryable_upstream_error_returns_502(tmp_path):
    transport, calls = make_transport([httpx.Response(401, json={"error": "nope"})])
    app = create_app(
        db_path=tmp_path / "pilot.sqlite3",
        upstream_url="https://example.test/customers",
        upstream_transport=transport,
        retry_delay_seconds=0,
    )
    with TestClient(app) as client:
        response = client.post("/sync")
        assert response.status_code == 502
        assert "HTTP 401" in response.json()["detail"]
        assert calls["count"] == 1
