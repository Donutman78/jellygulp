import httpx

from .config import settings


async def send_ntfy(message: str, title: str = "JellyGulp") -> None:
    if not settings.ntfy_topic:
        return

    url = f"{settings.ntfy_url.rstrip('/')}/{settings.ntfy_topic}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            url,
            content=message.encode("utf-8"),
            headers={"Title": title, "Tags": "clapper"},
        )
