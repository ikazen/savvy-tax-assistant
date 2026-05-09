from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.api.app import create_app
from savvy.config import get_settings
from savvy.storage.models import ClientCommunication, ClientKind, Entity
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
        await s.execute(delete(ClientCommunication))
        await s.execute(delete(Entity))
        await s.commit()


async def _create_entity(
    session_factory: async_sessionmaker[AsyncSession], name: str = "테스트"
) -> Entity:
    async with session_factory() as s:
        e = Entity(tenant_id="default", kind=ClientKind.CORP, name=name)
        s.add(e)
        await s.commit()
        await s.refresh(e)
        return e


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "channel": "kakao",
        "direction": "incoming",
        "occurred_at": datetime.now(UTC).isoformat(),
        "content": "안녕하세요, 부가세 신고 관련 문의드립니다.",
    }
    base.update(overrides)
    return base


async def test_record_and_get_communication(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    entity = await _create_entity(session_factory)
    resp = await client.post(
        f"/api/v1/entities/{entity.id}/communications",
        json=_payload(source_id="msg-1"),
    )
    assert resp.status_code == 201, resp.text
    cid = resp.json()["id"]

    fetched = await client.get(f"/api/v1/communications/{cid}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["channel"] == "kakao"
    assert body["entity_id"] == str(entity.id)


async def test_record_with_unknown_entity_returns_404(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/v1/entities/{uuid4()}/communications", json=_payload()
    )
    assert resp.status_code == 404


async def test_duplicate_source_id_returns_409(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    entity = await _create_entity(session_factory)
    payload = _payload(source_id="dup-1")
    r1 = await client.post(
        f"/api/v1/entities/{entity.id}/communications", json=payload
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/v1/entities/{entity.id}/communications", json=payload
    )
    assert r2.status_code == 409


async def test_list_filters_by_channel(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    entity = await _create_entity(session_factory)
    await client.post(
        f"/api/v1/entities/{entity.id}/communications",
        json=_payload(channel="kakao"),
    )
    await client.post(
        f"/api/v1/entities/{entity.id}/communications",
        json=_payload(channel="email"),
    )
    await client.post(
        f"/api/v1/entities/{entity.id}/communications",
        json=_payload(channel="email"),
    )

    resp = await client.get(
        f"/api/v1/entities/{entity.id}/communications?channel=email"
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_delete_communication(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    entity = await _create_entity(session_factory)
    create = await client.post(
        f"/api/v1/entities/{entity.id}/communications", json=_payload()
    )
    cid = create.json()["id"]
    assert (await client.delete(f"/api/v1/communications/{cid}")).status_code == 204
    assert (await client.get(f"/api/v1/communications/{cid}")).status_code == 404
