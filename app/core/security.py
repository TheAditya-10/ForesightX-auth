from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(ValueError):
    """Raised when a JWT token cannot be decoded or validated."""


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_token(
    *,
    subject: str,
    settings: Settings,
    token_type: str,
    expires_delta: timedelta,
    session_id: str,
    additional_claims: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + expires_delta
    jti = str(uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "sid": session_id,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if additional_claims:
        payload.update(additional_claims)

    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    token_type = payload.get("type")
    if token_type not in {"access", "refresh"}:
        raise TokenError("Unsupported token type")
    if not payload.get("sub") or not payload.get("jti") or not payload.get("sid"):
        raise TokenError("Malformed token payload")
    return payload
