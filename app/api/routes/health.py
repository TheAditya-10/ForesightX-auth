from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_redis_service
from app.services.redis_service import RedisService


router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    session: AsyncSession = Depends(get_db_session),
    redis_service: RedisService = Depends(get_redis_service),
) -> dict[str, object]:
    await session.execute(text("SELECT 1"))
    redis_ok = await redis_service.ping()
    return {
        "service": "foresightx-auth",
        "status": "ok" if redis_ok else "degraded",
        "database": "ok",
        "redis": "ok" if redis_ok else "down",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
