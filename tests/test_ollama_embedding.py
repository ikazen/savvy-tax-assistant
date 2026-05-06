from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from savvy.embedding.ollama import OllamaEmbedding


@pytest.mark.asyncio
async def test_embed_sends_input_list_and_parses_vectors():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "model": "bge-m3",
                "embeddings": [
                    [0.1, 0.2, 0.3],
                    [0.4, 0.5, 0.6],
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    emb = OllamaEmbedding(
        model="bge-m3",
        dimension=1024,
        base_url="http://localhost:11434",
        transport=transport,
    )

    vectors = await emb.embed(["hello", "world"])

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert captured["url"] == "http://localhost:11434/api/embed"
    assert captured["body"] == {"model": "bge-m3", "input": ["hello", "world"]}
    assert "authorization" not in {k.lower() for k in captured["headers"]}


@pytest.mark.asyncio
async def test_embed_empty_input_skips_request():
    transport = httpx.MockTransport(lambda r: pytest.fail("should not be called"))
    emb = OllamaEmbedding(model="bge-m3", dimension=1024, transport=transport)
    assert await emb.embed([]) == []


@pytest.mark.asyncio
async def test_embed_uses_authorization_header_for_cloud():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"embeddings": [[0.0]]})

    transport = httpx.MockTransport(handler)
    emb = OllamaEmbedding(
        model="bge-m3",
        dimension=1024,
        base_url="https://ollama.com",
        api_key="sk-cloud-key",
        transport=transport,
    )
    await emb.embed(["x"])

    assert captured["headers"]["authorization"] == "Bearer sk-cloud-key"


def test_dimension_and_model_id_properties():
    emb = OllamaEmbedding(model="bge-m3", dimension=1024)
    assert emb.dimension == 1024
    assert emb.model_id == "bge-m3"
