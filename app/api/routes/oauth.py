from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.responses import RedirectResponse

from app.api.deps import get_auth_service
from app.services.auth_service import AuthService


router = APIRouter(prefix="/oauth", tags=["oauth"])


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
    return await auth_service.handle_google_callback(userinfo)


# Backward-compatible alias.
@router.get("/google/login", include_in_schema=False)
async def google_login(request: Request) -> RedirectResponse:
    return await google_authorize(request)
