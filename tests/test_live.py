"""실제 외부 API(Ollama / Gemini)에 호출하는 라이브 검증 테스트.

opt-in: `uv run pytest -m live`
스킵 조건: 각 provider 키/연결이 없으면 해당 테스트만 스킵.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.config import get_settings
from savvy.embedding.factory import make_embedding
from savvy.llm.base import Message, Role
from savvy.llm.factory import make_llm
from savvy.storage.models import VectorEmbedding
from savvy.vectorstore import VectorRecord
from savvy.vectorstore.factory import make_vector_store
from tests.conftest import requires_db, requires_gemini, requires_ollama

pytestmark = [pytest.mark.live]


@requires_ollama
async def test_live_chat() -> None:
    settings = get_settings()
    llm = make_llm(settings)
    resp = await llm.chat(
        [Message(role=Role.USER, content="한 문장으로 자기소개 해줘.")]
    )
    assert resp.content.strip(), "빈 응답이 돌아옴"
    assert resp.finish_reason  # "stop" 또는 유사값


@requires_gemini
async def test_live_embedding_dimension_matches_settings() -> None:
    settings = get_settings()
    emb = make_embedding(settings)
    vectors = await emb.embed(
        ["법인세는 사업소득에 부과된다.", "tax consulting is hard"]
    )
    assert len(vectors) == 2
    assert all(len(v) == settings.embed_dimension for v in vectors), (
        f"임베딩 차원이 EMBED_DIMENSION({settings.embed_dimension})과 다름 — "
        f"실제: {[len(v) for v in vectors]}"
    )


@pytest_asyncio.fixture
async def live_namespace(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[str]:
    ns = f"live_{uuid.uuid4().hex[:8]}"
    yield ns
    async with session_factory() as session:
        await session.execute(
            delete(VectorEmbedding).where(VectorEmbedding.namespace == ns)
        )
        await session.commit()


@requires_db
@requires_gemini
async def test_live_e2e_embed_upsert_search(
    session_factory: async_sessionmaker[AsyncSession],
    live_namespace: str,
) -> None:
    """실제 임베딩 → pgvector 저장 → 시맨틱 검색이 의미적으로 동작하는지."""
    settings = get_settings()
    emb = make_embedding(settings)
    store = make_vector_store(settings, session_factory, emb.model_id)

    docs = [
        ("corp", "법인세는 법인의 사업소득에 부과되는 세금이다."),
        ("vat", "부가가치세는 상품과 서비스의 거래 단계에서 부과된다."),
        ("lunch", "오늘 점심은 김치찌개와 된장찌개 중에 고민했다."),
    ]
    vectors = await emb.embed([text for _, text in docs])
    records = [
        VectorRecord(id=doc_id, vector=vec, payload={"text": text})
        for (doc_id, text), vec in zip(docs, vectors, strict=True)
    ]
    await store.upsert(live_namespace, records)

    query_vec = (await emb.embed(["법인의 세금"]))[0]
    hits = await store.search(live_namespace, query_vec, k=3)

    assert len(hits) == 3
    # 'corp'가 가장 가까워야 의미 검색이 동작한 것
    assert hits[0].id == "corp", f"top hit이 corp가 아님: {[h.id for h in hits]}"
    # 'lunch'가 가장 멀어야 함 (관련 없는 문장)
    assert hits[-1].id == "lunch", f"bottom hit이 lunch가 아님: {[h.id for h in hits]}"
