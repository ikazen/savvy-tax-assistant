from __future__ import annotations

from savvy.config import Settings
from savvy.embedding.base import EmbeddingProvider
from savvy.embedding.gemini import GeminiEmbedding
from savvy.embedding.ollama import OllamaEmbedding


def make_embedding(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "ollama":
        return OllamaEmbedding(
            model=settings.ollama_embed_model,
            dimension=settings.embed_dimension,
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key or None,
        )
    if settings.embedding_provider == "gemini":
        return GeminiEmbedding(
            model=settings.gemini_embed_model,
            dimension=settings.embed_dimension,
            api_key=settings.gemini_api_key,
        )
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
