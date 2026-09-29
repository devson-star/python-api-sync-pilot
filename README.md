# Python/API automation pilot

A small paid-pilot style sample for a freelance Python/API integration: fetch a JSON array from an upstream REST endpoint, normalize and validate records, retry transient failures, idempotently upsert into SQLite, and expose both JSON and CSV outputs through FastAPI.

## Why this sample

It demonstrates a common shape of short freelance Python/API work: REST API integration, automation, backend endpoints, a database, tests, and handoff documentation. It deliberately uses a fixed configured upstream URL rather than accepting arbitrary URLs from callers.

## Run in 3 steps

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
PILOT_UPSTREAM_URL='https://your-api.example/items' uvicorn app.main:app --reload
```

Windows activation is `.venv\Scripts\activate`.

## API

- `GET /health` â€” health check.
- `POST /sync` â€” pulls the configured upstream endpoint. Retries 429/5xx/network failures up to 3 attempts, rejects invalid rows, and returns inserted/updated/unchanged/rejected counts.
- `GET /records` â€” normalized records from SQLite.
- `GET /records.csv` â€” deterministic CSV export.

Expected upstream shape:

```json
[
  {"id": "cust-1", "name": "Alice Example", "status": "active"},
  {"id": "cust-2", "name": "Bob Example", "status": "pending"}
]
```

Accepted statuses are `active`, `inactive`, and `pending`. Duplicate `id` values update in place, so rerunning a sync is safe.

## Verification

```bash
pytest -q
```

The tests use `httpx.MockTransport`, so they make no real network requests. Coverage includes a transient 503 followed by success, input rejection, idempotent re-sync, an update, CSV export, missing configuration, and a non-retryable 401.

## Handoff notes

For a real client, the adapter would be narrowed to their exact authentication and payload contract, secrets would stay in environment/secret storage, and SQLite could be replaced with PostgreSQL without changing the normalization and sync semantics.

