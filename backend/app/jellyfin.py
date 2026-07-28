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

    async def _post(self, path: str) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{self.base_url}{path}", headers=self.headers)
            response.raise_for_status()

    async def _content_folders(self) -> list[dict]:
        folders = await self.virtual_folders()
        excluded = settings.excluded_library_names_set
        return [
            folder
            for folder in folders
            if str(folder.get("Name") or "").strip().lower() not in excluded
            and str(folder.get("CollectionType") or "").lower() in {"movies", "tvshows"}
            and folder.get("ItemId")
        ]

    async def pause_session(self, session_id: str) -> None:
        await self._post(f"/Sessions/{quote(session_id)}/Playing/Pause")

    async def stop_session(self, session_id: str) -> None:
        await self._post(f"/Sessions/{quote(session_id)}/Playing/Stop")

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
        excluded = settings.excluded_library_names_set

        folders = [
            folder
            for folder in folders
            if str(folder.get("Name") or "").strip().lower() not in excluded
        ]

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

    async def recently_added(self, limit: int = 20) -> list[dict]:
        content_folders = await self._content_folders()

        async def fetch(parent_id: str) -> list[dict]:
            result = await self._get(
                "/Items",
                params={
                    "ParentId": parent_id,
                    "SortBy": "DateCreated",
                    "SortOrder": "Descending",
                    "IncludeItemTypes": "Movie,Episode",
                    "Recursive": "true",
                    "IsVirtualItem": "false",
                    "Limit": limit,
                    "Fields": "DateCreated,SeriesName,SeriesId,SeriesPrimaryImageTag,"
                    "ParentIndexNumber,IndexNumber,ImageTags",
                },
            )
            return result.get("Items", [])

        batches = (
            await asyncio.gather(*(fetch(folder["ItemId"]) for folder in content_folders))
            if content_folders
            else []
        )

        items = [item for batch in batches for item in batch]
        items.sort(key=lambda item: item.get("DateCreated") or "", reverse=True)
        return items[:limit]

    async def storage_breakdown(self) -> dict:
        content_folders = await self._content_folders()
        movie_folders = [
            f for f in content_folders if str(f.get("CollectionType") or "").lower() == "movies"
        ]
        tv_folders = [
            f for f in content_folders if str(f.get("CollectionType") or "").lower() == "tvshows"
        ]

        async def fetch_movies(parent_id: str) -> list[dict]:
            result = await self._get(
                "/Items",
                params={
                    "ParentId": parent_id,
                    "IncludeItemTypes": "Movie",
                    "Recursive": "true",
                    "IsVirtualItem": "false",
                    "Fields": "MediaSources",
                    "Limit": 5000,
                },
            )
            return result.get("Items", [])

        async def fetch_episodes(parent_id: str) -> list[dict]:
            result = await self._get(
                "/Items",
                params={
                    "ParentId": parent_id,
                    "IncludeItemTypes": "Episode",
                    "Recursive": "true",
                    "IsVirtualItem": "false",
                    "Fields": "MediaSources,SeriesName",
                    "Limit": 20000,
                },
            )
            return result.get("Items", [])

        movie_batches = (
            await asyncio.gather(*(fetch_movies(f["ItemId"]) for f in movie_folders))
            if movie_folders
            else []
        )
        episode_batches = (
            await asyncio.gather(*(fetch_episodes(f["ItemId"]) for f in tv_folders))
            if tv_folders
            else []
        )

        def item_bytes(item: dict) -> int:
            sources = item.get("MediaSources") or []
            return sum(s.get("Size") or 0 for s in sources)

        movies = [item for batch in movie_batches for item in batch]
        episodes = [item for batch in episode_batches for item in batch]

        movie_rows = sorted(
            (
                {"name": m.get("Name") or "Unknown", "bytes": item_bytes(m)}
                for m in movies
            ),
            key=lambda r: r["bytes"],
            reverse=True,
        )

        show_bytes: dict[str, int] = {}
        for e in episodes:
            series = e.get("SeriesName") or "Unknown"
            show_bytes[series] = show_bytes.get(series, 0) + item_bytes(e)
        show_rows = sorted(
            ({"name": name, "bytes": total} for name, total in show_bytes.items()),
            key=lambda r: r["bytes"],
            reverse=True,
        )

        return {
            "movies": movie_rows,
            "shows": show_rows,
            "movies_bytes": sum(r["bytes"] for r in movie_rows),
            "shows_bytes": sum(r["bytes"] for r in show_rows),
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
