from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from savvy.api.app import create_app


async def test_health_returns_ok() -> None:
    app = create_app()
    async with (
        # lifespan="auto" 로 startup/shutdown 트리거
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client
    ):
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
