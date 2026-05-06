from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.config import Settings
from savvy.vectorstore.base import VectorStore
from savvy.vectorstore.pgvector import PgVectorStore


def make_vector_store(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    embedding_model_id: str,
) -> VectorStore:
    if settings.vector_store == "pgvector":
        return PgVectorStore(session_factory=session_factory, model_id=embedding_model_id)
    if settings.vector_store in ("qdrant", "milvus"):
        raise NotImplementedError(f"{settings.vector_store} not yet implemented")
    raise ValueError(f"Unknown vector store: {settings.vector_store}")
