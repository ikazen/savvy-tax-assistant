from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.api.app import create_app
from savvy.config import get_settings
from savvy.storage.models import (
    ChatMessage,
    ChatSession,
    ClientKind,
    Entity,
    MessageRole,
)
from tests.conftest import requires_db

pytestmark = requires_db


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.state.session_factory = session_factory
    app.state.settings = get_settings()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    yield
    async with session_factory() as s:
        await s.execute(delete(ChatMessage))
        await s.execute(delete(ChatSession))
        await s.execute(delete(Entity))
        await s.commit()


async def _create_entity(
    session_factory: async_sessionmaker[AsyncSession],
) -> Entity:
    async with session_factory() as s:
        entity = Entity(tenant_id="default", kind=ClientKind.CORP, name="테스트법인")
        s.add(entity)
        await s.commit()
        await s.refresh(entity)
        return entity


async def test_create_chat_session_without_entity(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/chat-sessions", json={"title": "일반 상담"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "일반 상담"
    assert body["entity_id"] is None


async def test_create_chat_session_with_entity(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    entity = await _create_entity(session_factory)
    resp = await client.post(
        "/api/v1/chat-sessions",
        json={"entity_id": str(entity.id), "title": "법인 상담"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["entity_id"] == str(entity.id)


async def test_create_session_with_unknown_entity_returns_404(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/chat-sessions",
        json={"entity_id": str(uuid4())},
    )
    assert resp.status_code == 404


async def test_list_filter_by_entity(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    e1 = await _create_entity(session_factory)
    # E2를 만들기 위해 다른 엔티티
    async with session_factory() as s:
        e2 = Entity(tenant_id="default", kind=ClientKind.INDIVIDUAL, name="개인1")
        s.add(e2)
        await s.commit()
        e2_id = str(e2.id)

    await client.post(
        "/api/v1/chat-sessions", json={"entity_id": str(e1.id), "title": "for e1"}
    )
    await client.post(
        "/api/v1/chat-sessions", json={"entity_id": e2_id, "title": "for e2"}
    )
    await client.post("/api/v1/chat-sessions", json={"title": "general"})

    resp = await client.get(f"/api/v1/chat-sessions?entity_id={e1.id}")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["title"] == "for e1"


async def test_patch_session_title(client: AsyncClient) -> None:
    create = await client.post("/api/v1/chat-sessions", json={"title": "원래"})
    sid = create.json()["id"]
    resp = await client.patch(f"/api/v1/chat-sessions/{sid}", json={"title": "변경"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "변경"


async def test_delete_session(client: AsyncClient) -> None:
    create = await client.post("/api/v1/chat-sessions", json={})
    sid = create.json()["id"]
    assert (await client.delete(f"/api/v1/chat-sessions/{sid}")).status_code == 204
    assert (await client.get(f"/api/v1/chat-sessions/{sid}")).status_code == 404


async def test_list_messages_in_chronological_order(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    create = await client.post("/api/v1/chat-sessions", json={})
    sid = create.json()["id"]

    # 메시지는 아직 API 없으니 직접 DB로 삽입
    async with session_factory() as s:
        s.add_all(
            [
                ChatMessage(
                    session_id=sid, role=MessageRole.USER, content="안녕"
                ),
                ChatMessage(
                    session_id=sid, role=MessageRole.ASSISTANT, content="네, 안녕하세요"
                ),
            ]
        )
        await s.commit()

    resp = await client.get(f"/api/v1/chat-sessions/{sid}/messages")
    assert resp.status_code == 200
    msgs = resp.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


async def test_list_messages_unknown_session_404(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/chat-sessions/{uuid4()}/messages")
    assert resp.status_code == 404
