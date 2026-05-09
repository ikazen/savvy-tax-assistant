from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from savvy.config import get_settings
from savvy.storage.init_db import init_db


def _db_reachable(url: str) -> bool:
    async def _ping() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_ping())
    except Exception:
        return False


_DB_URL = get_settings().database_url
_DB_AVAILABLE = _db_reachable(_DB_URL)

requires_db = pytest.mark.skipif(
    not _DB_AVAILABLE,
    reason=f"Postgres not reachable at {_DB_URL}",
)


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    if _DB_AVAILABLE:
        await init_db()
    eng = create_async_engine(_DB_URL, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
