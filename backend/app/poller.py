import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from .config import settings
from .database import SessionLocal
from .jellyfin import JellyfinClient
from .models import PlaybackEvent


def ticks_to_seconds(value: int | None) -> float:
    return float(value or 0) / 10_000_000


class SessionPoller:
    def __init__(self) -> None:
        self.client = JellyfinClient()
        self.active: dict[str, dict] = {}
        self.running = False

    def normalize(self, session: dict) -> dict | None:
        now_playing = session.get("NowPlayingItem")
        play_state = session.get("PlayState") or {}
        if not now_playing:
            return None

        session_id = session.get("Id")
        if not session_id:
            return None

        media_source = (now_playing.get("MediaSources") or [{}])[0]
        transcoding = session.get("TranscodingInfo") or {}
        play_method = play_state.get("PlayMethod") or (
            "Transcode" if transcoding else "Unknown"
        )

        return {
            "session_id": session_id,
            "user_id": session.get("UserId"),
            "user_name": session.get("UserName"),
            "item_id": now_playing.get("Id"),
            "item_name": now_playing.get("Name"),
            "series_name": now_playing.get("SeriesName"),
            "item_type": now_playing.get("Type"),
            "client": session.get("Client"),
            "device_name": session.get("DeviceName"),
            "play_method": play_method,
            "position_seconds": ticks_to_seconds(play_state.get("PositionTicks")),
            "runtime_seconds": ticks_to_seconds(now_playing.get("RunTimeTicks")),
            "is_paused": bool(play_state.get("IsPaused")),
            "video_codec": media_source.get("VideoType") or transcoding.get("VideoCodec"),
            "bitrate": transcoding.get("Bitrate"),
        }

    def record(self, data: dict, event_type: str) -> None:
        with SessionLocal() as db:
            event = PlaybackEvent(
                session_id=data["session_id"],
                user_id=data.get("user_id"),
                user_name=data.get("user_name"),
                item_id=data.get("item_id"),
                item_name=data.get("item_name"),
                series_name=data.get("series_name"),
                item_type=data.get("item_type"),
                client=data.get("client"),
                device_name=data.get("device_name"),
                play_method=data.get("play_method"),
                position_seconds=data.get("position_seconds", 0),
                runtime_seconds=data.get("runtime_seconds", 0),
                event_type=event_type,
                occurred_at=datetime.now(timezone.utc),
            )
            db.add(event)
            db.commit()

    async def poll_once(self) -> None:
        sessions = await self.client.sessions()
        current = {}

        for raw in sessions:
            item = self.normalize(raw)
            if not item:
                continue
            sid = item["session_id"]
            current[sid] = item

            previous = self.active.get(sid)
            if previous is None:
                self.record(item, "started")
            elif previous.get("is_paused") != item.get("is_paused"):
                self.record(item, "paused" if item["is_paused"] else "resumed")

        for sid, previous in self.active.items():
            if sid not in current:
                self.record(previous, "stopped")

        self.active = current

    async def run(self) -> None:
        self.running = True
        while self.running:
            try:
                await self.poll_once()
            except Exception as exc:
                print(f"Session poll failed: {exc}", flush=True)
            await asyncio.sleep(max(settings.poll_interval_seconds, 5))

    def stop(self) -> None:
        self.running = False
