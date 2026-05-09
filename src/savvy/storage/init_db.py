from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from savvy.config import get_settings
from savvy.storage.models import Base


async def init_db() -> None:
    """스키마를 멱등하게 초기화.

    - pgvector extension 생성
    - SQLAlchemy 모델 기반 테이블 생성 (CREATE TABLE IF NOT EXISTS)
    - HNSW 인덱스 생성 (SQLAlchemy로는 표현 불가하므로 raw SQL)
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_vector_embeddings_hnsw "
                    "ON vector_embeddings USING hnsw (vector vector_cosine_ops)"
                )
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
