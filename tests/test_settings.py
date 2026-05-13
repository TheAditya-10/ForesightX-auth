from __future__ import annotations

from app.core.config import Settings


def test_settings_defaults_session_secret_to_jwt_secret() -> None:
    settings = Settings(_env_file=None, jwt_secret="secret-123", session_secret=None)
    assert settings.session_secret == "secret-123"


def test_settings_parses_cors_origins_csv() -> None:
    settings = Settings(_env_file=None, cors_origins="http://a.com, http://b.com ,")
    assert settings.cors_origins == ["http://a.com", "http://b.com"]


def test_google_oauth_enabled_requires_client_and_secret() -> None:
    assert Settings(_env_file=None, google_client_id="", google_client_secret="").google_oauth_enabled is False
    assert Settings(_env_file=None, google_client_id="id", google_client_secret="").google_oauth_enabled is False
    assert Settings(_env_file=None, google_client_id="", google_client_secret="sec").google_oauth_enabled is False
    assert Settings(_env_file=None, google_client_id="id", google_client_secret="sec").google_oauth_enabled is True


def test_settings_accepts_cors_origins_json_list() -> None:
    settings = Settings(_env_file=None, cors_origins=["http://a.com"])
    assert settings.cors_origins == ["http://a.com"]
