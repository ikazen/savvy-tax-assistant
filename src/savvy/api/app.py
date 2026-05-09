from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from savvy.api.routers.entities import router as entities_router
from savvy.api.routers.persons import router as persons_router
from savvy.config import get_settings
from savvy.storage.db import make_engine, make_session_factory

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """앱 수명 동안 단일 엔진/세션 팩토리 보유."""
    settings = get_settings()
    engine = make_engine(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Savvy Tax Assistant", lifespan=lifespan)

    @app.get(f"{API_PREFIX}/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(entities_router, prefix=API_PREFIX)
    app.include_router(persons_router, prefix=API_PREFIX)

    return app


app = create_app()
