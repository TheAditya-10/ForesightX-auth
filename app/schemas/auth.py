from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserRead


class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20)


class TokenPayload(BaseModel):
    sub: str
    type: str
    jti: str
    sid: str
    exp: int
    iat: int
    email: EmailStr | None = None
    role: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime


class AuthResponse(BaseModel):
    user: UserRead
    tokens: TokenPair


class VerifyResponse(BaseModel):
    valid: bool = True
    user: UserRead
