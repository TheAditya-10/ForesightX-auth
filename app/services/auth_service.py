from uuid import UUID, uuid4

from authlib.oidc.core import UserInfo
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared import get_logger

from app.core.config import Settings
from app.core.security import TokenError, hash_password, verify_password
from app.db.models import User
from app.schemas.auth import AuthResponse
from app.schemas.user import UserCreate, UserRead
from app.services.profile_client import ProfileClient
from app.services.redis_service import RedisService
from app.services.token_service import TokenService


class AuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        session: AsyncSession,
        redis_service: RedisService,
        profile_client: ProfileClient,
    ) -> None:
        self.settings = settings
        self.session = session
        self.redis_service = redis_service
        self.profile_client = profile_client
        self.token_service = TokenService(settings=settings, redis_service=redis_service)
        self.logger = get_logger(settings.service_name, "auth")

    async def register_user(self, payload: UserCreate) -> AuthResponse:
        existing = await self._get_user_by_email(payload.email)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

        user = User(
            email=payload.email.lower(),
            hashed_password=hash_password(payload.password),
            auth_provider="local",
            is_verified=False,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        created_profile = await self.profile_client.create_profile(user_id=str(user.id), email=user.email)
        if not created_profile:
            self.logger.warning("User registered but profile bootstrap failed", extra={"user_id": str(user.id)})

        tokens = await self.token_service.issue_token_pair(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            session_id=str(uuid4()),
            metadata={"provider": "local"},
        )
        return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)

    async def authenticate_user(self, *, email: str, password: str) -> AuthResponse:
        user = await self._get_user_by_email(email)
        if user is None or user.hashed_password is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        tokens = await self.token_service.issue_token_pair(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            session_id=str(uuid4()),
            metadata={"provider": user.auth_provider},
        )
        return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)

    async def refresh_tokens(self, refresh_token: str) -> AuthResponse:
        try:
            payload = await self.token_service.validate_token(refresh_token, expected_type="refresh")
        except TokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        user = await self._get_user_by_id(payload.sub)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is unavailable")

        try:
            tokens = await self.token_service.rotate_refresh_token(
                current_refresh_token=refresh_token,
                user_id=str(user.id),
                email=user.email,
                role=user.role,
            )
        except TokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)

    async def logout(self, *, refresh_token: str, access_token: str | None = None) -> None:
        try:
            await self.token_service.revoke_refresh_token(refresh_token)
        except TokenError as exc:
            if "revoked" not in str(exc).lower():
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        if access_token:
            try:
                await self.token_service.blacklist_access_token(access_token)
            except TokenError:
                self.logger.info("Access token could not be blacklisted during logout")

    async def verify_access_token(self, access_token: str) -> UserRead:
        try:
            payload = await self.token_service.validate_token(access_token, expected_type="access")
        except TokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        user = await self._get_user_by_id(payload.sub)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is unavailable")
        return UserRead.model_validate(user)

    async def handle_google_callback(self, userinfo: UserInfo | dict) -> AuthResponse:
        email = str(userinfo.get("email", "")).lower()
        google_subject = str(userinfo.get("sub", ""))
        is_verified = bool(userinfo.get("email_verified"))

        if not email or not google_subject:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google account did not provide required user information",
            )

        user = await self._get_user_by_email(email)
        if user is None:
            user = User(
                email=email,
                hashed_password=None,
                google_subject=google_subject,
                auth_provider="google",
                is_verified=is_verified,
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

            created_profile = await self.profile_client.create_profile(user_id=str(user.id), email=user.email)
            if not created_profile:
                self.logger.warning("OAuth user registered but profile bootstrap failed", extra={"user_id": str(user.id)})
        else:
            user.google_subject = google_subject
            if is_verified:
                user.is_verified = True
            await self.session.commit()

        tokens = await self.token_service.issue_token_pair(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            session_id=str(uuid4()),
            metadata={"provider": "google"},
        )
        return AuthResponse(user=UserRead.model_validate(user), tokens=tokens)

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: str) -> User | None:
        result = await self.session.execute(select(User).where(User.id == UUID(user_id)))
        return result.scalar_one_or_none()
