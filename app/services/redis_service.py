import json
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from shared import get_logger

from app.core.config import Settings


class RedisService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis: Redis | None = None
        self.logger = get_logger(settings.service_name, "redis")

    async def connect(self) -> None:
        self.redis = Redis.from_url(self.settings.redis_url, decode_responses=True)
        await self.redis.ping()
        self.logger.info("Redis connection established")

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
            self.redis = None

    def _require_client(self) -> Redis:
        if self.redis is None:
            raise RuntimeError("Redis client is not initialized")
        return self.redis

    async def ping(self) -> bool:
        return bool(await self._require_client().ping())

    async def store_refresh_session(
        self,
        *,
        user_id: str,
        session_id: str,
        refresh_jti: str,
        expires_in: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "user_id": user_id,
            "refresh_jti": refresh_jti,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        client = self._require_client()
        await client.setex(self._refresh_key(session_id), expires_in, json.dumps(payload))
        await client.sadd(self._user_sessions_key(user_id), session_id)
        await client.expire(self._user_sessions_key(user_id), expires_in)

    async def get_refresh_session(self, session_id: str) -> dict[str, Any] | None:
        raw_value = await self._require_client().get(self._refresh_key(session_id))
        if raw_value is None:
            return None
        return json.loads(raw_value)

    async def rotate_refresh_session(
        self,
        *,
        user_id: str,
        session_id: str,
        current_jti: str,
        new_jti: str,
        expires_in: int,
    ) -> bool:
        existing = await self.get_refresh_session(session_id)
        if existing is None or existing.get("refresh_jti") != current_jti:
            return False
        metadata = existing.get("metadata") or {}
        await self.store_refresh_session(
            user_id=user_id,
            session_id=session_id,
            refresh_jti=new_jti,
            expires_in=expires_in,
            metadata=metadata,
        )
        return True

    async def revoke_refresh_session(self, user_id: str, session_id: str) -> None:
        client = self._require_client()
        await client.delete(self._refresh_key(session_id))
        await client.srem(self._user_sessions_key(user_id), session_id)

    async def blacklist_token(self, jti: str, expires_in: int) -> None:
        await self._require_client().setex(self._blacklist_key(jti), expires_in, "1")

    async def is_token_blacklisted(self, jti: str) -> bool:
        return bool(await self._require_client().exists(self._blacklist_key(jti)))

    def _refresh_key(self, session_id: str) -> str:
        return f"auth:refresh:{session_id}"

    def _blacklist_key(self, jti: str) -> str:
        return f"auth:blacklist:{jti}"

    def _user_sessions_key(self, user_id: str) -> str:
        return f"auth:user-sessions:{user_id}"
