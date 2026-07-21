import asyncio
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_image(
        self,
        item_id: str,
        image_type: str = "Primary",
        tag: str | None = None,
    ) -> tuple[bytes, str]:
        params = {}
        if tag:
            params["tag"] = tag

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self.base_url}/Items/{quote(item_id)}/Images/{quote(image_type)}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()

        content_type = response.headers.get("content-type", "image/jpeg")
        return response.content, content_type

    async def system_info(self):
        return await self._get("/System/Info")

    async def item_counts(self):
        return await self._get("/Items/Counts")

    async def virtual_folders(self) -> list[dict]:
        result = await self._get("/Library/VirtualFolders")
        return result if isinstance(result, list) else []

    async def count_items(
        self,
        item_type: str,
        parent_id: str,
    ) -> int:
        result = await self._get(
            "/Items",
            params={
                "ParentId": parent_id,
                "Recursive": "true",
                "IncludeItemTypes": item_type,
                "IsVirtualItem": "false",
                "EnableTotalRecordCount": "true",
                "Limit": 1,
                "Fields": "BasicSyncInfo",
            },
        )
        return int(result.get("TotalRecordCount", 0))

    async def media_counts(self) -> dict[str, int]:
        folders = await self.virtual_folders()

        movie_folders = [
            folder
            for folder in folders
            if str(folder.get("CollectionType") or "").lower() == "movies"
            and folder.get("ItemId")
        ]
        tv_folders = [
            folder
            for folder in folders
            if str(folder.get("CollectionType") or "").lower() == "tvshows"
            and folder.get("ItemId")
        ]

        movie_tasks = [
            self.count_items("Movie", folder["ItemId"])
            for folder in movie_folders
        ]
        series_tasks = [
            self.count_items("Series", folder["ItemId"])
            for folder in tv_folders
        ]
        episode_tasks = [
            self.count_items("Episode", folder["ItemId"])
            for folder in tv_folders
        ]

        movies = sum(await asyncio.gather(*movie_tasks)) if movie_tasks else 0
        series = sum(await asyncio.gather(*series_tasks)) if series_tasks else 0
        episodes = sum(await asyncio.gather(*episode_tasks)) if episode_tasks else 0

        return {
            "movies": movies,
            "series": series,
            "episodes": episodes,
        }

    async def users(self):
        return await self._get("/Users")

    async def sessions(self):
        return await self._get("/Sessions")

    def image_url(
        self,
        item_id: str | None,
        image_tag: str | None = None,
    ) -> str | None:
        if not item_id:
            return None

        url = f"/api/images/{quote(item_id)}"
        if image_tag:
            url += f"?tag={quote(image_tag)}"
        return url
