"""사용자 도메인 ORM 모델 스키마 검증.

검증 대상:
- 기본 INSERT/SELECT
- FK 관계 (Person ← Entity, Entity ← ChatSession, ChatSession ← ChatMessage,
            Entity ← ClientCommunication, ClientCommunication ← ClientCommunicationChunk)
- ENUM 컬럼 저장/조회
- JSONB 직렬화 (tool_calls, source_metadata)
- partial unique index 동작 (사업자번호 dedup, 외부 메시지 source_id dedup)
- ON DELETE CASCADE 동작
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.storage.models import (
    ChatMessage,
    ChatSession,
    ClientCommunication,
    ClientCommunicationChunk,
    ClientKind,
    CommChannel,
    CommDirection,
    Entity,
    MessageRole,
    Person,
)
from tests.conftest import requires_db

pytestmark = requires_db


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s
    # 테스트별 격리: 도메인 테이블 전체 비움 (FK 역순)
    async with session_factory() as s:
        await s.execute(delete(ClientCommunicationChunk))
        await s.execute(delete(ClientCommunication))
        await s.execute(delete(ChatMessage))
        await s.execute(delete(ChatSession))
        await s.execute(delete(Entity))
        await s.execute(delete(Person))
        await s.commit()


async def test_person_and_entity_with_owner(db_session: AsyncSession) -> None:
    person = Person(tenant_id="default", name="홍길동", phone="010-0000-0000")
    db_session.add(person)
    await db_session.flush()

    entity = Entity(
        tenant_id="default",
        kind=ClientKind.CORP,
        name="홍길동상사",
        external_id="123-45-67890",
        owner_person_id=person.id,
    )
    db_session.add(entity)
    await db_session.commit()

    loaded = (
        await db_session.execute(select(Entity).where(Entity.id == entity.id))
    ).scalar_one()
    assert loaded.kind == ClientKind.CORP
    assert loaded.owner_person_id == person.id
    assert loaded.external_id == "123-45-67890"


async def test_entity_external_id_partial_unique(db_session: AsyncSession) -> None:
    """동일 (tenant, external_id) 중복 입력은 막혀야 함."""
    e1 = Entity(
        tenant_id="default",
        kind=ClientKind.CORP,
        name="A상사",
        external_id="111-22-33333",
    )
    db_session.add(e1)
    await db_session.commit()

    e2 = Entity(
        tenant_id="default",
        kind=ClientKind.CORP,
        name="B상사",
        external_id="111-22-33333",
    )
    db_session.add(e2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_entity_null_external_id_allowed_multiple(
    db_session: AsyncSession,
) -> None:
    """external_id가 null이면 여러 row 허용 (partial unique 의도)."""
    db_session.add_all(
        [
            Entity(tenant_id="default", kind=ClientKind.INDIVIDUAL, name="A"),
            Entity(tenant_id="default", kind=ClientKind.INDIVIDUAL, name="B"),
        ]
    )
    await db_session.commit()


async def test_chat_session_with_messages(db_session: AsyncSession) -> None:
    session = ChatSession(tenant_id="default", title="세금 상담")
    db_session.add(session)
    await db_session.flush()

    db_session.add_all(
        [
            ChatMessage(
                session_id=session.id,
                role=MessageRole.USER,
                content="법인세 절세 방법은?",
            ),
            ChatMessage(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                content="",
                tool_calls=[
                    {"id": "tc1", "name": "search_tax_law", "arguments": {"q": "법인세"}}
                ],
                model_id="gpt-oss:20b",
                token_usage={"prompt": 100, "completion": 20, "total": 120},
            ),
        ]
    )
    await db_session.commit()

    msgs = (
        await db_session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
        )
    ).scalars().all()
    assert len(msgs) == 2
    assert msgs[0].role == MessageRole.USER
    assert msgs[1].tool_calls[0]["name"] == "search_tax_law"
    assert msgs[1].token_usage == {"prompt": 100, "completion": 20, "total": 120}


async def test_client_communication_dedup_by_source_id(
    db_session: AsyncSession,
) -> None:
    entity = Entity(tenant_id="default", kind=ClientKind.CORP, name="X상사")
    db_session.add(entity)
    await db_session.flush()

    db_session.add(
        ClientCommunication(
            tenant_id="default",
            entity_id=entity.id,
            channel=CommChannel.KAKAO,
            direction=CommDirection.INCOMING,
            occurred_at=datetime.now(UTC),
            content="안녕하세요",
            source_id="kakao-msg-001",
        )
    )
    await db_session.commit()

    db_session.add(
        ClientCommunication(
            tenant_id="default",
            entity_id=entity.id,
            channel=CommChannel.KAKAO,
            direction=CommDirection.INCOMING,
            occurred_at=datetime.now(UTC),
            content="중복",
            source_id="kakao-msg-001",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_client_communication_chunks_cascade(
    db_session: AsyncSession,
) -> None:
    entity = Entity(tenant_id="default", kind=ClientKind.CORP, name="Y상사")
    db_session.add(entity)
    await db_session.flush()

    comm = ClientCommunication(
        tenant_id="default",
        entity_id=entity.id,
        channel=CommChannel.NOTE,
        direction=CommDirection.NOTE,
        occurred_at=datetime.now(UTC),
        content="회의록 전문...",
    )
    db_session.add(comm)
    await db_session.flush()

    db_session.add_all(
        [
            ClientCommunicationChunk(
                communication_id=comm.id, text="청크1", chunk_idx=0
            ),
            ClientCommunicationChunk(
                communication_id=comm.id, text="청크2", chunk_idx=1
            ),
        ]
    )
    await db_session.commit()

    # comm 삭제 → chunks도 cascade로 삭제
    await db_session.execute(
        delete(ClientCommunication).where(ClientCommunication.id == comm.id)
    )
    await db_session.commit()

    remaining = (
        await db_session.execute(
            select(ClientCommunicationChunk).where(
                ClientCommunicationChunk.communication_id == comm.id
            )
        )
    ).scalars().all()
    assert remaining == []
