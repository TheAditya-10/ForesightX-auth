from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.core.security import TokenError, create_token, decode_token
from app.schemas.auth import TokenPair, TokenPayload
from app.services.redis_service import RedisService


class TokenService:
    def __init__(self, settings: Settings, redis_service: RedisService) -> None:
        self.settings = settings
        self.redis_service = redis_service

    async def issue_token_pair(
        self,
        *,
        user_id: str,
        email: str,
        role: str,
        session_id: str,
        metadata: dict[str, str] | None = None,
    ) -> TokenPair:
        access_token, _, access_expires_at = create_token(
            subject=user_id,
            settings=self.settings,
            token_type="access",
            expires_delta=timedelta(minutes=self.settings.access_token_expire_minutes),
            session_id=session_id,
            additional_claims={"email": email, "role": role},
        )
        refresh_token, refresh_jti, refresh_expires_at = create_token(
            subject=user_id,
            settings=self.settings,
            token_type="refresh",
            expires_delta=timedelta(days=self.settings.refresh_token_expire_days),
            session_id=session_id,
            additional_claims={"email": email, "role": role},
        )
        refresh_ttl = max(int((refresh_expires_at - datetime.now(timezone.utc)).total_seconds()), 1)
        await self.redis_service.store_refresh_session(
            user_id=user_id,
            session_id=session_id,
            refresh_jti=refresh_jti,
            expires_in=refresh_ttl,
            metadata=metadata,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=access_expires_at,
            refresh_token_expires_at=refresh_expires_at,
        )

    async def rotate_refresh_token(
        self,
        *,
        current_refresh_token: str,
        user_id: str,
        email: str,
        role: str,
    ) -> TokenPair:
        payload = await self.validate_token(current_refresh_token, expected_type="refresh")
        refresh_token, new_refresh_jti, refresh_expires_at = create_token(
            subject=user_id,
            settings=self.settings,
            token_type="refresh",
            expires_delta=timedelta(days=self.settings.refresh_token_expire_days),
            session_id=payload.sid,
            additional_claims={"email": email, "role": role},
        )
        access_token, _, access_expires_at = create_token(
            subject=user_id,
            settings=self.settings,
            token_type="access",
            expires_delta=timedelta(minutes=self.settings.access_token_expire_minutes),
            session_id=payload.sid,
            additional_claims={"email": email, "role": role},
        )

        refresh_ttl = max(int((refresh_expires_at - datetime.now(timezone.utc)).total_seconds()), 1)
        rotated = await self.redis_service.rotate_refresh_session(
            user_id=user_id,
            session_id=payload.sid,
            current_jti=payload.jti,
            new_jti=new_refresh_jti,
            expires_in=refresh_ttl,
        )
        if not rotated:
            raise TokenError("Refresh session is invalid or has already been rotated")

        old_refresh_ttl = max(payload.exp - int(datetime.now(timezone.utc).timestamp()), 1)
        await self.redis_service.blacklist_token(payload.jti, old_refresh_ttl)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=access_expires_at,
            refresh_token_expires_at=refresh_expires_at,
        )

    async def validate_token(self, token: str, *, expected_type: str) -> TokenPayload:
        payload = TokenPayload.model_validate(decode_token(token, self.settings))
        if payload.type != expected_type:
            raise TokenError(f"Expected {expected_type} token")
        if await self.redis_service.is_token_blacklisted(payload.jti):
            raise TokenError("Token has been revoked")
        if expected_type == "refresh":
            session = await self.redis_service.get_refresh_session(payload.sid)
            if session is None or session.get("refresh_jti") != payload.jti:
                raise TokenError("Refresh session is invalid")
        return payload

    async def revoke_refresh_token(self, refresh_token: str) -> TokenPayload:
        payload = await self.validate_token(refresh_token, expected_type="refresh")
        ttl = max(payload.exp - int(datetime.now(timezone.utc).timestamp()), 1)
        await self.redis_service.blacklist_token(payload.jti, ttl)
        await self.redis_service.revoke_refresh_session(payload.sub, payload.sid)
        return payload

    async def blacklist_access_token(self, access_token: str) -> None:
        payload = await self.validate_token(access_token, expected_type="access")
        ttl = max(payload.exp - int(datetime.now(timezone.utc).timestamp()), 1)
        await self.redis_service.blacklist_token(payload.jti, ttl)
