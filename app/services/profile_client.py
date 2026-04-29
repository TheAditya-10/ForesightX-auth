import asyncio

import httpx

from shared import get_logger

from app.core.config import Settings


class ProfileClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client
        self.logger = get_logger(settings.service_name, "profile-client")

    async def create_profile(
        self,
        *,
        user_id: str,
        email: str,
        name: str | None = None,
        phone: str | None = None,
        pan: str | None = None,
        city: str | None = None,
        photo: str | None = None,
        risk_level: str | None = None,
    ) -> bool:
        url = f"{self.settings.profile_service_url.rstrip('/')}{self.settings.profile_create_path}"
        payload = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "phone": phone,
            "pan": pan,
            "city": city,
            "photo": photo,
            "risk_level": risk_level,
        }
        payload = {key: value for key, value in payload.items() if value is not None}

        for attempt in range(self.settings.http_max_retries + 1):
            try:
                response = await self.http_client.post(url, json=payload)
                response.raise_for_status()
                return True
            except httpx.HTTPError as exc:
                if attempt == self.settings.http_max_retries:
                    self.logger.warning(
                        "Profile bootstrap failed after retries",
                        extra={"url": url, "user_id": user_id, "error": str(exc)},
                    )
                    return False
                await asyncio.sleep(0.5 * (attempt + 1))

        return False
