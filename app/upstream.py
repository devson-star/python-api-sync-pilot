from __future__ import annotations

import asyncio
from typing import Any

import httpx


class UpstreamError(RuntimeError):
    pass


class UpstreamClient:
    def __init__(
        self,
        url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.05,
    ) -> None:
        self.url = url
        self.transport = transport
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds

    async def fetch_records(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0) as client:
            last_error = "upstream request failed"
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = await client.get(self.url)
                except httpx.RequestError as exc:
                    last_error = f"network error: {exc.__class__.__name__}"
                else:
                    if response.status_code < 400:
                        payload = response.json()
                        if not isinstance(payload, list):
                            raise UpstreamError("upstream payload must be a JSON array")
                        return payload
                    last_error = f"upstream returned HTTP {response.status_code}"
                    if response.status_code < 500 and response.status_code != 429:
                        break

                if attempt < self.max_attempts:
                    await asyncio.sleep(self.base_delay_seconds * attempt)

        raise UpstreamError(last_error)
