from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.storage.models import VectorEmbedding
from savvy.vectorstore.base import SearchHit, VectorRecord


class PgVectorStore:
    """pgvector-backed VectorStore.

    namespace + id 가 복합 기본키. 같은 id라도 namespace가 다르면 별개 레코드.
    score는 cosine similarity (1 - cosine_distance), 클수록 유사.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        model_id: str,
    ) -> None:
        self._session_factory = session_factory
        self._model_id = model_id

    async def upsert(
        self,
        namespace: str,
        records: Sequence[VectorRecord],
    ) -> None:
        if not records:
            return
        rows = [
            {
                "namespace": namespace,
                "id": r.id,
                "vector": r.vector,
                "payload": r.payload,
                "model_id": self._model_id,
            }
            for r in records
        ]
        stmt = pg_insert(VectorEmbedding).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["namespace", "id"],
            set_={
                "vector": stmt.excluded.vector,
                "payload": stmt.excluded.payload,
                "model_id": stmt.excluded.model_id,
            },
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def search(
        self,
        namespace: str,
        query_vector: list[float],
        k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        distance = VectorEmbedding.vector.cosine_distance(query_vector)
        stmt = (
            select(
                VectorEmbedding.id,
                VectorEmbedding.payload,
                distance.label("distance"),
            )
            .where(VectorEmbedding.namespace == namespace)
        )
        if filter:
            for key, value in filter.items():
                stmt = stmt.where(VectorEmbedding.payload[key].astext == str(value))
        stmt = stmt.order_by(distance).limit(k)

        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

        return [
            SearchHit(
                id=row.id,
                score=1.0 - float(row.distance),
                payload=dict(row.payload),
            )
            for row in rows
        ]

    async def delete(
        self,
        namespace: str,
        ids: Sequence[str],
    ) -> None:
        if not ids:
            return
        stmt = delete(VectorEmbedding).where(
            VectorEmbedding.namespace == namespace,
            VectorEmbedding.id.in_(list(ids)),
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()
