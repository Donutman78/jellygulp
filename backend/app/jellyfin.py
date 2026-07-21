from urllib.parse import quote

import httpx

from .config import settings


class JellyfinClient:
    def __init__(self) -> None:
        self.base_url = settings.jellyfin_url.rstrip("/")
        self.headers = {
            "X-Emby-Token": settings.jellyfin_api_key,
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: dict | None = None):
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def system_info(self):
        return await self._get("/System/Info")

    async def item_counts(self):
        return await self._get("/Items/Counts")

    async def users(self):
        return await self._get("/Users")

    async def sessions(self):
        return await self._get("/Sessions")

    def image_url(self, item_id: str | None, image_tag: str | None = None) -> str | None:
        if not item_id:
            return None
        url = f"{self.base_url}/Items/{quote(item_id)}/Images/Primary"
        if image_tag:
            url += f"?tag={quote(image_tag)}"
        return url
