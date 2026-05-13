from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core.config import Settings
from app.core.security import TokenError
from app.services.token_service import TokenService


class _FakeRedis:
    def __init__(self) -> None:
        self.refresh_sessions: dict[str, dict[str, Any]] = {}
        self.blacklisted: set[str] = set()
        self.user_sessions: dict[str, set[str]] = {}

    async def store_refresh_session(
        self,
        *,
        user_id: str,
        session_id: str,
        refresh_jti: str,
        expires_in: int,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.refresh_sessions[session_id] = {
            "user_id": user_id,
            "refresh_jti": refresh_jti,
            "expires_in": expires_in,
            "metadata": metadata or {},
        }
        self.user_sessions.setdefault(user_id, set()).add(session_id)

    async def get_refresh_session(self, session_id: str) -> dict[str, Any] | None:
        return self.refresh_sessions.get(session_id)

    async def rotate_refresh_session(
        self,
        *,
        user_id: str,
        session_id: str,
        current_jti: str,
        new_jti: str,
        expires_in: int,
    ) -> bool:
        existing = self.refresh_sessions.get(session_id)
        if existing is None or existing.get("refresh_jti") != current_jti:
            return False
        await self.store_refresh_session(
            user_id=user_id,
            session_id=session_id,
            refresh_jti=new_jti,
            expires_in=expires_in,
            metadata=existing.get("metadata") or {},
        )
        return True

    async def revoke_refresh_session(self, user_id: str, session_id: str) -> None:
        self.refresh_sessions.pop(session_id, None)
        self.user_sessions.get(user_id, set()).discard(session_id)

    async def blacklist_token(self, jti: str, expires_in: int) -> None:  # noqa: ARG002
        self.blacklisted.add(jti)

    async def is_token_blacklisted(self, jti: str) -> bool:
        return jti in self.blacklisted


def test_issue_validate_rotate_revoke_token_pair() -> None:
    async def _run() -> None:
        settings = Settings(
            _env_file=None,
            jwt_secret="secret-123",
            session_secret="secret-123",
            access_token_expire_minutes=1,
            refresh_token_expire_days=1,
        )
        redis = _FakeRedis()
        service = TokenService(settings=settings, redis_service=redis)  # type: ignore[arg-type]

        pair = await service.issue_token_pair(
            user_id="user-1",
            email="u@example.com",
            role="user",
            session_id="session-1",
        )
        assert pair.access_token and pair.refresh_token
        assert redis.refresh_sessions["session-1"]["user_id"] == "user-1"

        refresh_payload = await service.validate_token(pair.refresh_token, expected_type="refresh")
        assert refresh_payload.sub == "user-1"
        assert refresh_payload.sid == "session-1"

        rotated = await service.rotate_refresh_token(
            current_refresh_token=pair.refresh_token,
            user_id="user-1",
            email="u@example.com",
            role="user",
        )
        assert rotated.refresh_token != pair.refresh_token
        assert refresh_payload.jti in redis.blacklisted

        revoked_payload = await service.revoke_refresh_token(rotated.refresh_token)
        assert revoked_payload.sub == "user-1"
        assert await redis.get_refresh_session("session-1") is None

    asyncio.run(_run())


def test_validate_token_rejects_blacklisted_access_token() -> None:
    async def _run() -> None:
        settings = Settings(_env_file=None, jwt_secret="secret-123")
        redis = _FakeRedis()
        service = TokenService(settings=settings, redis_service=redis)  # type: ignore[arg-type]
        pair = await service.issue_token_pair(
            user_id="user-1",
            email="u@example.com",
            role="user",
            session_id="session-1",
        )
        access_payload = await service.validate_token(pair.access_token, expected_type="access")
        await redis.blacklist_token(access_payload.jti, expires_in=60)
        with pytest.raises(TokenError, match="revoked"):
            await service.validate_token(pair.access_token, expected_type="access")

    asyncio.run(_run())
