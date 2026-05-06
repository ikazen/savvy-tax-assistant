from __future__ import annotations

import math
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.config import get_settings
from savvy.storage.models import VectorEmbedding
from savvy.vectorstore import VectorRecord
from savvy.vectorstore.pgvector import PgVectorStore
from tests.conftest import requires_db

pytestmark = requires_db


def _unit(vec: list[float]) -> list[float]:
    """단위 벡터로 정규화 (cosine similarity 검증을 단순화)."""
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


def _pad(vec: list[float]) -> list[float]:
    """모델 차원에 맞춰 0으로 패딩."""
    dim = get_settings().embed_dimension
    out = list(vec) + [0.0] * (dim - len(vec))
    return _unit(out)


@pytest_asyncio.fixture
async def store(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[tuple[PgVectorStore, str]]:
    namespace = f"test_{uuid.uuid4().hex[:8]}"
    s = PgVectorStore(session_factory=session_factory, model_id="test-embed")
    yield s, namespace

    # 클린업: 해당 네임스페이스 전체 삭제
    async with session_factory() as session:
        await session.execute(
            delete(VectorEmbedding).where(VectorEmbedding.namespace == namespace)
        )
        await session.commit()


async def test_upsert_and_search_returns_nearest_first(
    store: tuple[PgVectorStore, str],
):
    s, ns = store
    a = _pad([1.0, 0.0, 0.0])
    b = _pad([0.0, 1.0, 0.0])
    c = _pad([0.9, 0.1, 0.0])

    await s.upsert(
        ns,
        [
            VectorRecord(id="a", vector=a, payload={"label": "A"}),
            VectorRecord(id="b", vector=b, payload={"label": "B"}),
            VectorRecord(id="c", vector=c, payload={"label": "C"}),
        ],
    )

    hits = await s.search(ns, query_vector=a, k=2)

    assert [h.id for h in hits] == ["a", "c"]
    assert hits[0].score > hits[1].score
    # 자기 자신은 코사인 유사도 ~ 1.0
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)
    assert hits[0].payload == {"label": "A"}


async def test_upsert_updates_existing_record(
    store: tuple[PgVectorStore, str],
):
    s, ns = store
    v1 = _pad([1.0, 0.0])
    v2 = _pad([0.0, 1.0])

    await s.upsert(ns, [VectorRecord(id="x", vector=v1, payload={"v": 1})])
    await s.upsert(ns, [VectorRecord(id="x", vector=v2, payload={"v": 2})])

    hits = await s.search(ns, query_vector=v2, k=1)

    assert hits[0].id == "x"
    assert hits[0].payload == {"v": 2}


async def test_search_filter_by_payload_equality(
    store: tuple[PgVectorStore, str],
):
    s, ns = store
    q = _pad([1.0, 0.0])

    await s.upsert(
        ns,
        [
            VectorRecord(id="1", vector=q, payload={"category": "law", "year": "2025"}),
            VectorRecord(id="2", vector=q, payload={"category": "case", "year": "2025"}),
            VectorRecord(id="3", vector=q, payload={"category": "law", "year": "2024"}),
        ],
    )

    hits = await s.search(ns, query_vector=q, k=10, filter={"category": "law"})
    assert sorted(h.id for h in hits) == ["1", "3"]

    hits = await s.search(
        ns, query_vector=q, k=10, filter={"category": "law", "year": "2025"}
    )
    assert [h.id for h in hits] == ["1"]


async def test_namespace_isolation(
    session_factory: async_sessionmaker[AsyncSession],
):
    s = PgVectorStore(session_factory=session_factory, model_id="test-embed")
    ns_a = f"test_iso_a_{uuid.uuid4().hex[:6]}"
    ns_b = f"test_iso_b_{uuid.uuid4().hex[:6]}"
    v = _pad([1.0])

    try:
        await s.upsert(ns_a, [VectorRecord(id="x", vector=v, payload={"in": "A"})])
        await s.upsert(ns_b, [VectorRecord(id="x", vector=v, payload={"in": "B"})])

        hits_a = await s.search(ns_a, v, k=10)
        hits_b = await s.search(ns_b, v, k=10)

        assert len(hits_a) == 1 and hits_a[0].payload == {"in": "A"}
        assert len(hits_b) == 1 and hits_b[0].payload == {"in": "B"}
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(VectorEmbedding).where(VectorEmbedding.namespace.in_([ns_a, ns_b]))
            )
            await session.commit()


async def test_delete_removes_records(store: tuple[PgVectorStore, str]):
    s, ns = store
    v = _pad([1.0])

    await s.upsert(
        ns,
        [
            VectorRecord(id="a", vector=v),
            VectorRecord(id="b", vector=v),
            VectorRecord(id="c", vector=v),
        ],
    )
    await s.delete(ns, ["a", "c"])

    hits = await s.search(ns, v, k=10)
    assert [h.id for h in hits] == ["b"]


async def test_empty_inputs_short_circuit(store: tuple[PgVectorStore, str]):
    s, ns = store
    # 예외 없이 통과해야 함
    await s.upsert(ns, [])
    await s.delete(ns, [])
    hits = await s.search(ns, _pad([1.0]), k=5)
    assert hits == []
