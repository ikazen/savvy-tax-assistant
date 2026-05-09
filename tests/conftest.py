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


def _ollama_configured() -> bool:
    """Cloud는 키 존재로, 로컬은 핑으로 판단."""
    s = get_settings()
    if s.ollama_api_key:
        return True
    try:
        import httpx

        r = httpx.get(f"{s.ollama_base_url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not _ollama_configured(),
    reason="Ollama not configured (no API key, and local instance unreachable)",
)


def _gemini_configured() -> bool:
    return bool(get_settings().gemini_api_key)


requires_gemini = pytest.mark.skipif(
    not _gemini_configured(),
    reason="Gemini not configured (GEMINI_API_KEY empty)",
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
