from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.api.app import create_app
from savvy.config import get_settings
from savvy.storage.models import Entity, Person
from tests.conftest import requires_db

pytestmark = requires_db


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """conftest의 session-scoped engine을 재사용하기 위해 lifespan을 우회하고
    app.state에 직접 주입."""
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
        await s.execute(delete(Entity))
        await s.execute(delete(Person))
        await s.commit()


async def test_create_and_get_entity(client: AsyncClient) -> None:
    payload = {"kind": "corp", "name": "테스트법인", "external_id": "111-22-33333"}
    resp = await client.post("/api/v1/entities", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "corp"
    assert body["name"] == "테스트법인"
    assert body["tenant_id"] == "default"

    fetched = await client.get(f"/api/v1/entities/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["external_id"] == "111-22-33333"


async def test_list_entities_paginated(client: AsyncClient) -> None:
    for i in range(3):
        await client.post(
            "/api/v1/entities",
            json={"kind": "individual", "name": f"개인{i}"},
        )
    resp = await client.get("/api/v1/entities?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_patch_only_updates_provided_fields(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/entities",
        json={"kind": "corp", "name": "원래이름", "memo": "원래메모"},
    )
    eid = create.json()["id"]

    resp = await client.patch(f"/api/v1/entities/{eid}", json={"name": "변경후"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "변경후"
    assert body["kind"] == "corp"  # 유지
    assert body["memo"] == "원래메모"  # 유지


async def test_delete_entity_then_404(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/entities", json={"kind": "corp", "name": "삭제대상"}
    )
    eid = create.json()["id"]
    resp = await client.delete(f"/api/v1/entities/{eid}")
    assert resp.status_code == 204
    assert (await client.get(f"/api/v1/entities/{eid}")).status_code == 404


async def test_get_unknown_entity_returns_404(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/entities/{uuid4()}")
    assert resp.status_code == 404


async def test_create_with_invalid_kind_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/entities",
        json={"kind": "alien", "name": "이상한고객"},
    )
    assert resp.status_code == 422
