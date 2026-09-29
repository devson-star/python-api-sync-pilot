# Validation record

Date: 2026-09-28.

Environment: isolated Linux container. No third-party repository was executed on the user's Windows host.

## Checks

- `pytest -q` -> **4 passed**.
- `python -m compileall -q app tests` -> pass.
- `git diff --cached --check` over the complete sample -> pass.
- Extra normalization smoke assertion -> pass.

Installed sandbox versions used for the successful run:

- FastAPI 0.128.2
- httpx 0.28.1
- pytest 9.0.2
- uvicorn 0.48.0

The sandbox had no outbound DNS during the dependency-install attempt, so validation used the already-installed versions above. Tests use `httpx.MockTransport` and made no real upstream requests.

## Behaviors covered

1. Retry a transient HTTP 503 and then succeed.
2. Normalize whitespace/case and reject malformed rows.
3. Insert valid records into SQLite.
4. Re-sync the same data idempotently as unchanged.
5. Update a changed record.
6. Export deterministic CSV.
7. Fail clearly when no upstream is configured.
8. Return a 502 without retrying a non-retryable upstream 401.
