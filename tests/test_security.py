from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.config import Settings
from app.core.security import TokenError, create_token, decode_token, hash_password, verify_password


def test_password_hashing_round_trip() -> None:
    hashed = hash_password("Str0ng!Pass")
    assert verify_password("Str0ng!Pass", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_access_token_contains_required_claims() -> None:
    settings = Settings(_env_file=None, jwt_secret="secret-123", jwt_algorithm="HS256")
    token, jti, expires_at = create_token(
        subject="user-1",
        settings=settings,
        token_type="access",
        expires_delta=timedelta(minutes=5),
        session_id="session-1",
        additional_claims={"email": "u@example.com", "role": "user"},
    )
    payload = decode_token(token, settings)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"
    assert payload["sid"] == "session-1"
    assert payload["jti"] == jti
    assert payload["exp"] == int(expires_at.timestamp())
    assert payload["email"] == "u@example.com"
    assert payload["role"] == "user"


def test_decode_token_rejects_unsupported_type() -> None:
    settings = Settings(_env_file=None, jwt_secret="secret-123", jwt_algorithm="HS256")
    token, *_ = create_token(
        subject="user-1",
        settings=settings,
        token_type="weird",
        expires_delta=timedelta(minutes=1),
        session_id="session-1",
    )
    with pytest.raises(TokenError, match="Unsupported token type"):
        decode_token(token, settings)


def test_decode_token_rejects_expired_token() -> None:
    settings = Settings(_env_file=None, jwt_secret="secret-123", jwt_algorithm="HS256")
    token, *_ = create_token(
        subject="user-1",
        settings=settings,
        token_type="access",
        expires_delta=timedelta(seconds=-1),
        session_id="session-1",
    )
    with pytest.raises(TokenError, match="Invalid or expired"):
        decode_token(token, settings)
