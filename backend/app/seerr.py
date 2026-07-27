import asyncio

import httpx

from .config import settings

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w300"


class SeerrClient:
    def __init__(self) -> None:
        self.base_url = settings.seerr_url.rstrip("/")
        self.headers = {
            "X-Api-Key": settings.seerr_api_key,
            "Accept": "application/json",
        }

    @property
    def configured(self) -> bool:
        return bool(settings.seerr_url and settings.seerr_api_key)

    async def _get(self, path: str, params: dict | None = None):
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def _requests(self, filter_name: str, take: int = 50) -> list[dict]:
        result = await self._get(
            "/api/v1/request",
            params={"filter": filter_name, "take": take, "sort": "added"},
        )
        return result.get("results", [])

    async def _media_details(self, media_type: str, tmdb_id: int) -> dict:
        path = f"/api/v1/movie/{tmdb_id}" if media_type == "movie" else f"/api/v1/tv/{tmdb_id}"
        try:
            return await self._get(path)
        except Exception:
            return {}

    async def _enrich(self, requests: list[dict]) -> list[dict]:
        cache: dict[tuple[str, int], dict] = {}
        keys = {
            (item.get("type"), (item.get("media") or {}).get("tmdbId"))
            for item in requests
            if (item.get("media") or {}).get("tmdbId")
        }

        details_list = await asyncio.gather(
            *(self._media_details(media_type, tmdb_id) for media_type, tmdb_id in keys)
        )
        for (media_type, tmdb_id), details in zip(keys, details_list):
            cache[(media_type, tmdb_id)] = details

        enriched = []
        for item in requests:
            media = item.get("media") or {}
            tmdb_id = media.get("tmdbId")
            item_type = item.get("type")
            details = cache.get((item_type, tmdb_id), {}) if tmdb_id else {}

            title = details.get("title") or details.get("name") or "Unknown title"
            poster_path = details.get("posterPath")
            requested_by = item.get("requestedBy") or {}

            enriched.append({
                "id": item.get("id"),
                "type": item_type,
                "title": title,
                "poster_url": f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None,
                "requested_by": requested_by.get("displayName")
                or requested_by.get("jellyfinUsername")
                or requested_by.get("email"),
                "requested_at": item.get("createdAt"),
            })

        return enriched

    async def raw_requests(self, filter_name: str, take: int = 50) -> list[dict]:
        return await self._requests(filter_name, take)

    async def enrich(self, requests: list[dict]) -> list[dict]:
        return await self._enrich(requests)

    async def wishlist(self) -> list[dict]:
        requests = await self._requests("pending")
        return await self._enrich(requests)

    async def coming_soon(self) -> list[dict]:
        requests = await self._requests("processing")
        return await self._enrich(requests)
