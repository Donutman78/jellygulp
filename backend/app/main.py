import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text

from .config import settings
from .database import Base, SessionLocal, engine
from .jellyfin import JellyfinClient
from .models import PlaybackEvent
from .poller import SessionPoller, ticks_to_seconds

client = JellyfinClient()
poller = SessionPoller()
poller_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global poller_task
    Base.metadata.create_all(bind=engine)
    poller_task = asyncio.create_task(poller.run())
    yield
    poller.stop()
    if poller_task:
        poller_task.cancel()


app = FastAPI(title="JellyGulp API", version="0.1.0", lifespan=lifespan)

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


@app.get("/api/dashboard")
async def dashboard():
    try:
        system, counts, users, sessions = await asyncio.gather(
            client.system_info(),
            client.item_counts(),
            client.users(),
            client.sessions(),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Jellyfin request failed: {exc}") from exc

    active_sessions = []
    for session in sessions:
        item = session.get("NowPlayingItem")
        if not item:
            continue

        play_state = session.get("PlayState") or {}
        transcode = session.get("TranscodingInfo") or {}
        runtime = ticks_to_seconds(item.get("RunTimeTicks"))
        position = ticks_to_seconds(play_state.get("PositionTicks"))
        image_tags = item.get("ImageTags") or {}

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
            "progress_percent": round((position / runtime * 100), 1) if runtime else 0,
            "is_paused": bool(play_state.get("IsPaused")),
            "play_method": play_state.get("PlayMethod") or (
                "Transcode" if transcode else "Unknown"
            ),
            "video_codec": transcode.get("VideoCodec"),
            "audio_codec": transcode.get("AudioCodec"),
            "bitrate": transcode.get("Bitrate"),
            "image_url": client.image_url(item.get("Id"), image_tags.get("Primary")),
        })

    since = datetime.now(timezone.utc) - timedelta(days=30)
    with SessionLocal() as db:
        event_count = db.scalar(
            select(func.count(PlaybackEvent.id)).where(PlaybackEvent.occurred_at >= since)
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
            "movies": counts.get("MovieCount", 0),
            "series": counts.get("SeriesCount", 0),
            "episodes": counts.get("EpisodeCount", 0),
            "songs": counts.get("SongCount", 0),
            "albums": counts.get("AlbumCount", 0),
        },
        "users": {
            "total": len(users),
            "disabled": sum(1 for u in users if (u.get("Policy") or {}).get("IsDisabled")),
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
