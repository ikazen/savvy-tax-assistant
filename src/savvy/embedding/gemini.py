from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, cast

import httpx


class GeminiEmbedding:
    """Google Gemini embedding via Generative Language API (AI Studio).

    https://ai.google.dev/gemini-api/docs/embeddings

    출력 차원을 모델 기본보다 줄이면 unit norm이 깨진다 (Matryoshka 절단 특성).
    cosine 유사도 일관성을 위해 정규화 후 반환.
    """

    def __init__(
        self,
        model: str,
        dimension: int,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com",
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("GeminiEmbedding requires an API key")
        self._model = model
        self._dimension = dimension
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
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
        path = f"/v1beta/models/{self._model}:batchEmbedContents"
        payload = {
            "requests": [
                {
                    "model": f"models/{self._model}",
                    "content": {"parts": [{"text": t}]},
                    "outputDimensionality": self._dimension,
                }
                for t in texts
            ]
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            resp = await client.post(path, json=payload, headers=headers)
            resp.raise_for_status()
            data = cast(dict[str, Any], resp.json())

        return [_normalize(cast(list[float], emb["values"])) for emb in data["embeddings"]]


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]
