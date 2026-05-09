from __future__ import annotations

import json
import math
from typing import Any

import httpx
import pytest

from savvy.embedding.gemini import GeminiEmbedding


def _is_unit(vec: list[float], tol: float = 1e-6) -> bool:
    return abs(math.sqrt(sum(x * x for x in vec)) - 1.0) < tol


@pytest.mark.asyncio
async def test_embed_sends_batch_request_and_normalizes():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["headers"] = dict(request.headers)
        # 의도적으로 norm != 1인 벡터 반환 → GeminiEmbedding이 정규화해야 함
        return httpx.Response(
            200,
            json={
                "embeddings": [
                    {"values": [3.0, 4.0]},  # norm=5
                    {"values": [0.0, 2.0]},  # norm=2
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    emb = GeminiEmbedding(
        model="gemini-embedding-2",
        dimension=768,
        api_key="test-key",
        transport=transport,
    )

    vectors = await emb.embed(["hello", "world"])

    assert vectors == [[0.6, 0.8], [0.0, 1.0]]
    assert all(_is_unit(v) for v in vectors)
    assert captured["url"].endswith(
        "/v1beta/models/gemini-embedding-2:batchEmbedContents"
    )
    assert captured["body"] == {
        "requests": [
            {
                "model": "models/gemini-embedding-2",
                "content": {"parts": [{"text": "hello"}]},
                "outputDimensionality": 768,
            },
            {
                "model": "models/gemini-embedding-2",
                "content": {"parts": [{"text": "world"}]},
                "outputDimensionality": 768,
            },
        ]
    }
    assert captured["headers"]["x-goog-api-key"] == "test-key"


@pytest.mark.asyncio
async def test_embed_empty_input_skips_request():
    transport = httpx.MockTransport(lambda r: pytest.fail("should not be called"))
    emb = GeminiEmbedding(
        model="gemini-embedding-2",
        dimension=768,
        api_key="test-key",
        transport=transport,
    )
    assert await emb.embed([]) == []


def test_requires_api_key():
    with pytest.raises(ValueError, match="API key"):
        GeminiEmbedding(model="gemini-embedding-2", dimension=768, api_key="")


def test_dimension_and_model_id_properties():
    emb = GeminiEmbedding(
        model="gemini-embedding-2", dimension=768, api_key="test-key"
    )
    assert emb.dimension == 768
    assert emb.model_id == "gemini-embedding-2"
