from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_auth_service, get_current_user
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    VerifyResponse,
)
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/sign-up", response_model=AuthResponse, status_code=201)
async def sign_up(
    payload: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await auth_service.register_user(payload)


@router.post("/sign-in", response_model=AuthResponse)
async def sign_in(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await auth_service.authenticate_user(email=payload.email, password=payload.password)


@router.post("/token/refresh", response_model=AuthResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return await auth_service.refresh_tokens(payload.refresh_token)


@router.post("/sign-out", response_model=MessageResponse)
async def sign_out(
    payload: LogoutRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    access_token = credentials.credentials if credentials is not None else None
    await auth_service.logout(refresh_token=payload.refresh_token, access_token=access_token)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=VerifyResponse)
async def me(current_user: UserRead = Depends(get_current_user)) -> VerifyResponse:
    return VerifyResponse(user=current_user)


# Backward-compatible aliases kept for existing clients.
@router.post("/register", response_model=AuthResponse, status_code=201, include_in_schema=False)
async def register(payload: UserCreate, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return await sign_up(payload, auth_service)


@router.post("/login", response_model=AuthResponse, include_in_schema=False)
async def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return await sign_in(payload, auth_service)


@router.post("/refresh", response_model=AuthResponse, include_in_schema=False)
async def refresh(payload: RefreshTokenRequest, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return await refresh_token(payload, auth_service)


@router.post("/logout", response_model=MessageResponse, include_in_schema=False)
async def logout(
    payload: LogoutRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    return await sign_out(payload, credentials, auth_service)


@router.get("/verify", response_model=VerifyResponse, include_in_schema=False)
async def verify(current_user: UserRead = Depends(get_current_user)) -> VerifyResponse:
    return await me(current_user)
