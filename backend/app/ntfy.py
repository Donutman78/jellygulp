import httpx

from .config import settings


async def send_ntfy(message: str, title: str = "JellyGulp") -> bool:
    if not settings.ntfy_topic:
        return False

    url = f"{settings.ntfy_url.rstrip('/')}/{settings.ntfy_topic}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            content=message.encode("utf-8"),
            headers={"Title": title, "Tags": "clapper"},
        )

    if response.status_code != 200:
        print(
            f"ntfy send failed: {response.status_code} {response.text[:200]}",
            flush=True,
        )
        return False

    return True
