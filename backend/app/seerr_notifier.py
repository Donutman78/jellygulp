import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from .config import settings
from .database import SessionLocal
from .models import NotifiedSeerrEvent
from .ntfy import send_ntfy
from .seerr import SeerrClient

FILTER_BY_EVENT = {
    "requested": "pending",
    "approved": "processing",
    "available": "available",
}


def build_message(event_type: str, item: dict) -> tuple[str, str]:
    name = item.get("requested_by")

    if event_type == "requested":
        by = f" by {name}" if name else ""
        return "New JellyGulp request", f"{item['title']} was requested{by}."

    by = f" (requested by {name})" if name else ""
    if event_type == "approved":
        return "Request approved", f"{item['title']}{by} was approved and is queued to download."

    return "Now available", f"{item['title']}{by} is now available to watch."


class SeerrNotifier:
    def __init__(self) -> None:
        self.client = SeerrClient()
        self.running = False

    async def _notify_new(self, event_type: str) -> None:
        raw_items = await self.client.raw_requests(FILTER_BY_EVENT[event_type], take=50)
        ids = [item["id"] for item in raw_items if item.get("id") is not None]
        if not ids:
            return

        with SessionLocal() as db:
            known_ids = set(
                db.scalars(
                    select(NotifiedSeerrEvent.request_id).where(
                        NotifiedSeerrEvent.event_type == event_type,
                        NotifiedSeerrEvent.request_id.in_(ids),
                    )
                ).all()
            )

            new_raw = [item for item in raw_items if item["id"] not in known_ids]
            if not new_raw:
                return

            enriched = await self.client.enrich(new_raw)

            for item in enriched:
                title_header, message = build_message(event_type, item)
                await send_ntfy(message, title=title_header)
                db.add(
                    NotifiedSeerrEvent(
                        request_id=item["id"],
                        event_type=event_type,
                        notified_at=datetime.now(timezone.utc),
                    )
                )
            db.commit()

    async def check_once(self) -> None:
        for event_type in ("requested", "approved", "available"):
            await self._notify_new(event_type)

    async def run(self) -> None:
        if not self.client.configured:
            print("Seerr notifier disabled: SEERR_URL/SEERR_API_KEY not set", flush=True)
            return
        if not settings.ntfy_topic:
            print("Seerr notifier disabled: NTFY_TOPIC not set", flush=True)
            return

        print("Seerr notifier started, checking every 120s", flush=True)
        self.running = True
        while self.running:
            try:
                await self.check_once()
            except Exception as exc:
                print(f"Seerr notify check failed: {exc}", flush=True)
            await asyncio.sleep(120)

    def stop(self) -> None:
        self.running = False
