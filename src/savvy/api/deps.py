"""FastAPI Depends 헬퍼.

라우터에서 `session: SessionDep` 형태로 사용 (Annotated alias).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.llm.base import LLMProvider


def get_session_factory(
    request: Request,
) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory  # type: ignore[no-any-return]


SessionFactoryDep = Annotated[
    async_sessionmaker[AsyncSession], Depends(get_session_factory)
]


async def get_db(factory: SessionFactoryDep) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]


def get_llm(request: Request) -> LLMProvider:
    return request.app.state.llm  # type: ignore[no-any-return]


LLMDep = Annotated[LLMProvider, Depends(get_llm)]
