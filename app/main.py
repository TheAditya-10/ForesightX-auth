from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from shared import configure_logging, get_logger

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.oauth import router as oauth_router
from app.core.config import Settings, get_settings
from app.core.oauth import build_oauth_client
from app.db.session import check_database_connection, close_database, get_session_factory
from app.services.profile_client import ProfileClient
from app.services.redis_service import RedisService


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    settings = get_settings()
    configure_logging(settings.service_name, settings.log_level)
    logger = get_logger(settings.service_name, "startup")

    session_factory = get_session_factory(settings)
    redis_service = RedisService(settings)
    oauth = build_oauth_client(settings)
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(settings.request_timeout_seconds))
    profile_client = ProfileClient(settings=settings, http_client=http_client)

    await redis_service.connect()
    await check_database_connection(settings)

    app_instance.state.settings = settings
    app_instance.state.session_factory = session_factory
    app_instance.state.redis_service = redis_service
    app_instance.state.oauth = oauth
    app_instance.state.http_client = http_client
    app_instance.state.profile_client = profile_client
    logger.info("Auth service startup complete")

    try:
        yield
    finally:
        await http_client.aclose()
        await redis_service.close()
        await close_database()
        logger.info("Auth service shutdown complete")


def create_application(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    app_instance = FastAPI(
        title="ForesightX Auth Service",
        version="1.0.0",
        lifespan=lifespan,
    )

    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app_instance.add_middleware(
        SessionMiddleware,
        secret_key=active_settings.session_secret,
        same_site="lax",
        https_only=active_settings.environment.lower() == "production",
    )

    app_instance.include_router(auth_router)
    app_instance.include_router(oauth_router)
    app_instance.include_router(health_router)
    return app_instance


app = create_application()


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "service": get_settings().service_name,
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
