import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from .config import settings
from .database import SessionLocal
from .models import NotifiedSeerrRequest
from .ntfy import send_ntfy
from .seerr import SeerrClient


class SeerrNotifier:
    def __init__(self) -> None:
        self.client = SeerrClient()
        self.running = False

    async def check_once(self) -> None:
        items = await self.client.wishlist()
        if not items:
            return

        with SessionLocal() as db:
            known_ids = set(
                db.scalars(
                    select(NotifiedSeerrRequest.request_id).where(
                        NotifiedSeerrRequest.request_id.in_([item["id"] for item in items])
                    )
                ).all()
            )

            for item in items:
                if item["id"] in known_ids:
                    continue

                by = f" by {item['requested_by']}" if item.get("requested_by") else ""
                await send_ntfy(
                    f"{item['title']} was requested{by}.",
                    title="New JellyGulp request",
                )
                db.add(
                    NotifiedSeerrRequest(
                        request_id=item["id"],
                        notified_at=datetime.now(timezone.utc),
                    )
                )
            db.commit()

    async def run(self) -> None:
        if not self.client.configured or not settings.ntfy_topic:
            return

        self.running = True
        while self.running:
            try:
                await self.check_once()
            except Exception as exc:
                print(f"Seerr notify check failed: {exc}", flush=True)
            await asyncio.sleep(120)

    def stop(self) -> None:
        self.running = False
