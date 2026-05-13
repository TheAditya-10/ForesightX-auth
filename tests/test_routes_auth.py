from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service, get_current_user
from app.api.routes.auth import router as auth_router
from app.schemas.auth import AuthResponse, MessageResponse
from app.schemas.user import UserRead


class _AuthStub:
    async def register_user(self, payload):  # noqa: ANN001
        return self._auth_response(payload.email)

    async def authenticate_user(self, *, email: str, password: str):  # noqa: ARG002
        return self._auth_response(email)

    async def refresh_tokens(self, refresh_token: str):  # noqa: ARG002
        return self._auth_response("u@example.com")

    async def logout(self, *, refresh_token: str, access_token: str | None = None):  # noqa: ARG002
        return None

    async def verify_access_token(self, token: str):  # noqa: ARG002
        return self._user("u@example.com")

    def _user(self, email: str) -> UserRead:
        return UserRead(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email=email,
            role="user",
            auth_provider="local",
            is_active=True,
            is_verified=False,
            created_at=datetime.utcnow(),
        )

    def _auth_response(self, email: str) -> AuthResponse:
        user = self._user(email)
        return AuthResponse(
            user=user,
            tokens={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "access_token_expires_at": datetime.utcnow(),
                "refresh_token_expires_at": datetime.utcnow(),
            },
        )


def test_auth_routes_sign_in_and_me_and_sign_out() -> None:
    app = FastAPI()
    app.include_router(auth_router)
    stub = _AuthStub()

    app.dependency_overrides[get_auth_service] = lambda: stub

    async def _current_user_override():
        return stub._user("u@example.com")

    app.dependency_overrides[get_current_user] = _current_user_override
    client = TestClient(app)

    response = client.post("/auth/sign-in", json={"email": "u@example.com", "password": "Aa1!aaaa"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "u@example.com"
    assert body["tokens"]["access_token"] == "access-token"

    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "u@example.com"

    response = client.post(
        "/auth/sign-out",
        headers={"Authorization": "Bearer access-token"},
        json={"refresh_token": "x" * 20},
    )
    assert response.status_code == 200
    assert MessageResponse.model_validate(response.json()).message
