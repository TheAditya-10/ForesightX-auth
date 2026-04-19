from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.schemas.user import UserRead
from app.services.auth_service import AuthService
from app.services.profile_client import ProfileClient
from app.services.redis_service import RedisService


bearer_scheme = HTTPBearer(auto_error=False)


def get_settings_dependency(request: Request) -> Settings:
    return request.app.state.settings


def get_redis_service(request: Request) -> RedisService:
    return request.app.state.redis_service


def get_profile_client(request: Request) -> ProfileClient:
    return request.app.state.profile_client


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def get_auth_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> AuthService:
    return AuthService(
        settings=request.app.state.settings,
        session=session,
        redis_service=request.app.state.redis_service,
        profile_client=request.app.state.profile_client,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserRead:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return await auth_service.verify_access_token(credentials.credentials)
