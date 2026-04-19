from authlib.integrations.starlette_client import OAuth

from app.core.config import Settings


def build_oauth_client(settings: Settings) -> OAuth:
    oauth = OAuth()
    if settings.google_oauth_enabled:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    return oauth
