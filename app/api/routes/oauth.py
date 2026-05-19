import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.responses import HTMLResponse, RedirectResponse

from app.api.deps import get_auth_service
from app.schemas.auth import AuthResponse
from app.services.auth_service import AuthService


router = APIRouter(prefix="/oauth", tags=["oauth"])


def build_oauth_html_response(auth_response: AuthResponse, redirect_path: str) -> HTMLResponse:
        session_payload = {
                "accessToken": auth_response.tokens.access_token,
                "refreshToken": auth_response.tokens.refresh_token,
                "user": {
                        "id": str(auth_response.user.id),
                        "email": auth_response.user.email,
                        "role": auth_response.user.role,
                },
        }
        html = f"""<!doctype html>
<html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <meta http-equiv=\"Cache-Control\" content=\"no-store\" />
        <meta http-equiv=\"Pragma\" content=\"no-cache\" />
        <title>Signing you in…</title>
    </head>
    <body>
        <p>Signing you in…</p>
        <script>
            (function () {{
                try {{
                    const session = {json.dumps(session_payload)};
                    localStorage.setItem("fx_session", JSON.stringify(session));
                    window.location.replace("{redirect_path}");
                }} catch (err) {{
                    console.error("OAuth session storage failed", err);
                }}
            }})();
        </script>
    </body>
</html>
"""
        return HTMLResponse(
                content=html,
                headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )


@router.get("/google/authorize")
async def google_authorize(request: Request) -> RedirectResponse:
    settings = request.app.state.settings
    if not settings.google_oauth_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth is not configured")

    google = request.app.state.oauth.create_client("google")
    redirect_uri = settings.google_redirect_uri or request.url_for("google_callback")
    return await google.authorize_redirect(request, str(redirect_uri))


@router.get("/google/callback", name="google_callback")
async def google_callback(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    settings = request.app.state.settings
    if not settings.google_oauth_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth is not configured")

    google = request.app.state.oauth.create_client("google")
    token = await google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if userinfo is None:
        userinfo = await google.parse_id_token(request, token)
    if userinfo is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to retrieve Google user info")
    auth_response = await auth_service.handle_google_callback(userinfo)
    accept_header = request.headers.get("accept", "")
    wants_html = "text/html" in accept_header or "application/xhtml+xml" in accept_header
    redirect_path = request.query_params.get("next") or "/dashboard/profile"
    if not redirect_path.startswith("/"):
        redirect_path = "/dashboard/profile"
    if wants_html:
        return build_oauth_html_response(auth_response, redirect_path)
    return auth_response


# Backward-compatible alias.
@router.get("/google/login", include_in_schema=False)
async def google_login(request: Request) -> RedirectResponse:
    return await google_authorize(request)
