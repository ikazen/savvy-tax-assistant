from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.api.app import create_app
from savvy.config import get_settings
from savvy.storage.models import Person
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
        await s.execute(delete(Person))
        await s.commit()


async def test_create_and_get_person(client: AsyncClient) -> None:
    payload = {"name": "홍길동", "phone": "010-0000-0000"}
    resp = await client.post("/api/v1/persons", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "홍길동"
    assert body["tenant_id"] == "default"

    fetched = await client.get(f"/api/v1/persons/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["phone"] == "010-0000-0000"


async def test_list_persons_paginated(client: AsyncClient) -> None:
    for i in range(3):
        await client.post("/api/v1/persons", json={"name": f"P{i}"})
    resp = await client.get("/api/v1/persons?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_patch_only_updates_provided_fields(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/persons", json={"name": "원래", "memo": "원래메모"}
    )
    pid = create.json()["id"]

    resp = await client.patch(f"/api/v1/persons/{pid}", json={"name": "변경"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "변경"
    assert body["memo"] == "원래메모"


async def test_delete_person_then_404(client: AsyncClient) -> None:
    create = await client.post("/api/v1/persons", json={"name": "삭제대상"})
    pid = create.json()["id"]
    assert (await client.delete(f"/api/v1/persons/{pid}")).status_code == 204
    assert (await client.get(f"/api/v1/persons/{pid}")).status_code == 404


async def test_get_unknown_person_returns_404(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/persons/{uuid4()}")
    assert resp.status_code == 404
