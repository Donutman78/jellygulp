import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import func, select, text

from .config import settings
from .database import Base, SessionLocal, engine
from .jellyfin import JellyfinClient
from .models import PlaybackEvent
from .poller import SessionPoller, ticks_to_seconds

client = JellyfinClient()
poller = SessionPoller()
poller_task: asyncio.Task | None = None


def human_resolution(width: int | None, height: int | None) -> str | None:
    if height:
        if height >= 2160:
            return "4K"
        if height >= 1440:
            return "1440p"
        if height >= 1080:
            return "1080p"
        if height >= 720:
            return "720p"
        return f"{height}p"

    if width:
        if width >= 3840:
            return "4K"
        if width >= 2560:
            return "1440p"
        if width >= 1920:
            return "1080p"
        if width >= 1280:
            return "720p"

    return None


def first_stream(media_streams: list[dict], stream_type: str) -> dict:
    return next(
        (stream for stream in media_streams if stream.get("Type") == stream_type),
        {},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global poller_task
    Base.metadata.create_all(bind=engine)
    poller_task = asyncio.create_task(poller.run())
    yield
    poller.stop()
    if poller_task:
        poller_task.cancel()


app = FastAPI(title="JellyGulp API", version="0.2.2", lifespan=lifespan)

origins = ["*"] if settings.cors_origins == "*" else [
    x.strip() for x in settings.cors_origins.split(",") if x.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    database_connected = False
    jellyfin_connected = False

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            database_connected = True
    except Exception:
        pass

    try:
        await client.system_info()
        jellyfin_connected = True
    except Exception:
        pass

    return {
        "status": "ok" if database_connected and jellyfin_connected else "degraded",
        "database_connected": database_connected,
        "jellyfin_connected": jellyfin_connected,
    }


@app.get("/api/images/{item_id}")
async def image_proxy(
    item_id: str,
    tag: str | None = Query(default=None),
):
    try:
        content, content_type = await client.get_image(
            item_id=item_id,
            image_type="Primary",
            tag=tag,
        )
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 404:
            raise HTTPException(status_code=404, detail="Image not found") from exc
        raise HTTPException(
            status_code=502,
            detail="Jellyfin image request failed",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Jellyfin image request failed",
        ) from exc

    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/dashboard")
async def dashboard():
    try:
        system, media_counts, generic_counts, users, sessions = await asyncio.gather(
            client.system_info(),
            client.media_counts(),
            client.item_counts(),
            client.users(),
            client.sessions(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Jellyfin request failed: {exc}",
        ) from exc

    active_sessions = []

    for session in sessions:
        item = session.get("NowPlayingItem")
        if not item:
            continue

        play_state = session.get("PlayState") or {}
        transcode = session.get("TranscodingInfo") or {}

        media_sources = item.get("MediaSources") or []
        media_source = media_sources[0] if media_sources else {}
        media_streams = media_source.get("MediaStreams") or []

        video_stream = first_stream(media_streams, "Video")
        audio_stream = first_stream(media_streams, "Audio")

        runtime = ticks_to_seconds(item.get("RunTimeTicks"))
        position = ticks_to_seconds(play_state.get("PositionTicks"))
        remaining = max(runtime - position, 0) if runtime else 0

        image_tags = item.get("ImageTags") or {}

        play_method = play_state.get("PlayMethod")
        if not play_method:
            if transcode:
                play_method = "Transcode"
            elif media_source:
                play_method = "Direct Play"
            else:
                play_method = "Unknown"

        width = (
            transcode.get("Width")
            or video_stream.get("Width")
            or media_source.get("Width")
        )
        height = (
            transcode.get("Height")
            or video_stream.get("Height")
            or media_source.get("Height")
        )

        video_range = (
            video_stream.get("VideoRangeType")
            or video_stream.get("VideoRange")
            or ""
        )
        is_hdr = str(video_range).upper() not in {"", "SDR", "UNKNOWN", "NONE"}

        bitrate = (
            transcode.get("Bitrate")
            or media_source.get("Bitrate")
            or video_stream.get("BitRate")
        )

        active_sessions.append({
            "session_id": session.get("Id"),
            "user_name": session.get("UserName") or "Unknown user",
            "client": session.get("Client") or "Unknown client",
            "device_name": session.get("DeviceName") or "Unknown device",
            "item_id": item.get("Id"),
            "title": item.get("Name"),
            "series_name": item.get("SeriesName"),
            "season_name": item.get("SeasonName"),
            "episode_number": item.get("IndexNumber"),
            "item_type": item.get("Type"),
            "position_seconds": position,
            "runtime_seconds": runtime,
            "remaining_seconds": remaining,
            "progress_percent": round((position / runtime * 100), 1) if runtime else 0,
            "is_paused": bool(play_state.get("IsPaused")),
            "play_method": play_method,
            "resolution": human_resolution(width, height),
            "width": width,
            "height": height,
            "is_hdr": is_hdr,
            "video_range": video_range or None,
            "video_codec": (
                transcode.get("VideoCodec")
                or video_stream.get("Codec")
            ),
            "audio_codec": (
                transcode.get("AudioCodec")
                or audio_stream.get("Codec")
            ),
            "audio_channels": (
                audio_stream.get("Channels")
                or audio_stream.get("ChannelLayout")
            ),
            "container": media_source.get("Container"),
            "bitrate": bitrate,
            "transcode_reasons": transcode.get("TranscodeReasons") or [],
            "image_url": client.image_url(
                item.get("Id"),
                image_tags.get("Primary"),
            ),
        })

    since = datetime.now(timezone.utc) - timedelta(days=30)

    with SessionLocal() as db:
        event_count = db.scalar(
            select(func.count(PlaybackEvent.id)).where(
                PlaybackEvent.occurred_at >= since
            )
        ) or 0

        starts_30d = db.scalar(
            select(func.count(PlaybackEvent.id)).where(
                PlaybackEvent.occurred_at >= since,
                PlaybackEvent.event_type == "started",
            )
        ) or 0

    return {
        "server": {
            "name": system.get("ServerName"),
            "version": system.get("Version"),
            "id": system.get("Id"),
            "operating_system": system.get("OperatingSystem"),
        },
        "counts": {
            "movies": media_counts["movies"],
            "series": media_counts["series"],
            "episodes": media_counts["episodes"],
            "songs": generic_counts.get("SongCount", 0),
            "albums": generic_counts.get("AlbumCount", 0),
        },
        "users": {
            "total": len(users),
            "disabled": sum(
                1
                for user in users
                if (user.get("Policy") or {}).get("IsDisabled")
            ),
        },
        "activity": {
            "active_streams": len(active_sessions),
            "recorded_events_30d": event_count,
            "play_starts_30d": starts_30d,
        },
        "sessions": active_sessions,
    }


@app.get("/api/history/recent")
async def recent_history(limit: int = 50):
    limit = max(1, min(limit, 200))

    with SessionLocal() as db:
        rows = db.scalars(
            select(PlaybackEvent)
            .order_by(PlaybackEvent.occurred_at.desc())
            .limit(limit)
        ).all()

    return [
        {
            "id": row.id,
            "user_name": row.user_name,
            "item_name": row.item_name,
            "series_name": row.series_name,
            "item_type": row.item_type,
            "client": row.client,
            "device_name": row.device_name,
            "play_method": row.play_method,
            "position_seconds": row.position_seconds,
            "runtime_seconds": row.runtime_seconds,
            "event_type": row.event_type,
            "occurred_at": row.occurred_at,
        }
        for row in rows
    ]
