from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from .store import NormalizedRecord, RecordStore
from .upstream import UpstreamClient, UpstreamError

ALLOWED_STATUSES = {"active", "inactive", "pending"}


def normalize(payload: dict[str, Any]) -> NormalizedRecord | None:
    external_id = str(payload.get("id", "")).strip()
    name = str(payload.get("name", "")).strip()
    status = str(payload.get("status", "pending")).strip().lower()
    if not external_id or not name or status not in ALLOWED_STATUSES:
        return None
    return NormalizedRecord(external_id=external_id, name=name, status=status)


def create_app(
    *,
    db_path: str | Path | None = None,
    upstream_url: str | None = None,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
    retry_delay_seconds: float = 0.05,
) -> FastAPI:
    path = db_path or os.environ.get("PILOT_DB_PATH", "pilot.sqlite3")
    url = upstream_url or os.environ.get("PILOT_UPSTREAM_URL")
    store = RecordStore(path)
    store.initialize()

    app = FastAPI(title="API Sync Pilot", version="0.1.0")
    app.state.store = store
    app.state.upstream_url = url
    app.state.upstream_transport = upstream_transport
    app.state.retry_delay_seconds = retry_delay_seconds

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/sync")
    async def sync() -> dict[str, int]:
        if not app.state.upstream_url:
            raise HTTPException(status_code=503, detail="PILOT_UPSTREAM_URL is not configured")

        client = UpstreamClient(
            app.state.upstream_url,
            transport=app.state.upstream_transport,
            base_delay_seconds=app.state.retry_delay_seconds,
        )
        try:
            raw_records = await client.fetch_records()
        except UpstreamError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        normalized: list[NormalizedRecord] = []
        rejected = 0
        for item in raw_records:
            if not isinstance(item, dict):
                rejected += 1
                continue
            record = normalize(item)
            if record is None:
                rejected += 1
            else:
                normalized.append(record)

        counts = store.upsert_many(normalized)
        return {**counts, "rejected": rejected, "received": len(raw_records)}

    @app.get("/records")
    def records() -> list[dict[str, str]]:
        return store.list_all()

    @app.get("/records.csv", response_class=PlainTextResponse)
    def records_csv() -> PlainTextResponse:
        return PlainTextResponse(
            store.as_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="records.csv"'},
        )

    return app


app = create_app()
