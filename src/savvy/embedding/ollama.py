from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import httpx


class OllamaEmbedding:
    """Ollama embedding provider — works for both local Ollama and Ollama Cloud."""

    def __init__(
        self,
        model: str,
        dimension: int,
        base_url: str = "http://localhost:11434",
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {"model": self._model, "input": list(texts)}
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            resp = await client.post("/api/embed", json=payload, headers=headers)
            resp.raise_for_status()
            data = cast(dict[str, Any], resp.json())
        return cast(list[list[float]], data["embeddings"])
