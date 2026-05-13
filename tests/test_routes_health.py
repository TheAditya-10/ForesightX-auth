from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db_session, get_redis_service
from app.api.routes.health import router as health_router


class _SessionStub:
    async def execute(self, _stmt):  # noqa: ANN001
        return None


class _RedisStub:
    def __init__(self, ok: bool) -> None:
        self.ok = ok

    async def ping(self) -> bool:
        return self.ok


def test_health_route_reports_ok_when_redis_ok() -> None:
    async def _run() -> None:
        app = FastAPI()
        app.include_router(health_router)

        async def _db_override():
            yield _SessionStub()

        app.dependency_overrides[get_db_session] = _db_override
        app.dependency_overrides[get_redis_service] = lambda: _RedisStub(True)

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["database"] == "ok"
        assert body["redis"] == "ok"
        assert body["status"] == "ok"

    asyncio.run(_run())


def test_health_route_reports_degraded_when_redis_down() -> None:
    async def _run() -> None:
        app = FastAPI()
        app.include_router(health_router)

        async def _db_override():
            yield _SessionStub()

        app.dependency_overrides[get_db_session] = _db_override
        app.dependency_overrides[get_redis_service] = lambda: _RedisStub(False)

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["redis"] == "down"
        assert body["status"] == "degraded"

    asyncio.run(_run())
