from collections import defaultdict
from datetime import timedelta

from .models import PlaybackEvent

SAFETY_GAP_HOURS = 6
FINISHED_THRESHOLD_PCT = 90
TOP_N = 8


def _cluster_sessions(events: list[PlaybackEvent]) -> list[dict]:
    """Collapse raw events into logical viewing sessions.

    Jellyfin session IDs can rotate on reconnect (browser refresh, app
    backgrounding), which would otherwise split one continuous watch into
    several recorded "started" events. A new session begins at a "started"
    event only if the previous one actually ended (a "stopped" was seen, or
    there wasn't a prior event) - a reconnect mid-watch just adds another
    "started" into the still-open session instead of starting a new one.

    A generous time-based safety net still applies in case a "stopped"
    genuinely never got recorded (e.g. an extended backend outage) so an
    unrelated rewatch days later isn't merged into a stale open session.
    """
    groups: dict[tuple, list[PlaybackEvent]] = defaultdict(list)
    for event in events:
        key = (event.user_id or event.user_name or "unknown", event.item_id or event.item_name or "unknown")
        groups[key].append(event)

    sessions = []
    for evs in groups.values():
        evs.sort(key=lambda e: e.occurred_at)
        cluster: list[PlaybackEvent] = []
        session_open = False

        for event in evs:
            long_gap = cluster and (event.occurred_at - cluster[-1].occurred_at) > timedelta(hours=SAFETY_GAP_HOURS)
            starts_new = not cluster or (event.event_type == "started" and not session_open) or long_gap

            if starts_new and cluster:
                sessions.append(_summarize_cluster(cluster))
                cluster = []

            cluster.append(event)
            if event.event_type == "stopped":
                session_open = False
            elif event.event_type in ("started", "paused", "resumed"):
                session_open = True

        if cluster:
            sessions.append(_summarize_cluster(cluster))

    return sessions


def _summarize_cluster(cluster: list[PlaybackEvent]) -> dict:
    first, last = cluster[0], cluster[-1]
    runtime = max((e.runtime_seconds or 0) for e in cluster)
    watched = max(0.0, (last.position_seconds or 0) - (first.position_seconds or 0))
    if runtime:
        watched = min(watched, runtime)

    completion_pct = (last.position_seconds / runtime * 100) if runtime else None

    return {
        "start": first.occurred_at,
        "title": first.series_name or first.item_name or "Unknown title",
        "user": first.user_name or "Unknown",
        "client": first.client or "Unknown",
        "item_type": first.item_type or "Unknown",
        "hours": watched / 3600,
        "is_play": any(e.event_type == "started" for e in cluster),
        "is_transcode": any("transcode" in (e.play_method or "").lower() for e in cluster),
        "completion_pct": completion_pct,
    }


def _media_bucket(item_type: str) -> str:
    if item_type == "Movie":
        return "movies"
    if item_type in ("Episode", "Series", "Season"):
        return "shows"
    return "other"


def _top(rows: dict[str, dict], key: str) -> list[dict]:
    ranked = sorted(rows.values(), key=lambda r: r["hours"], reverse=True)[:TOP_N]
    for row in ranked:
        row["hours"] = round(row["hours"], 2)
    return ranked


def build_analytics(events: list[PlaybackEvent], days: int) -> dict:
    sessions = _cluster_sessions(events)

    daily: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    by_user: dict[str, dict] = {}
    by_device: dict[str, dict] = {}
    heatmap: dict[tuple[int, int], int] = defaultdict(int)

    total_hours = 0.0
    transcode_hours = 0.0
    total_plays = 0
    finished = 0
    abandoned = 0
    users_seen: set[str] = set()
    media_hours: dict[str, float] = defaultdict(float)

    for s in sessions:
        total_hours += s["hours"]
        if s["is_transcode"]:
            transcode_hours += s["hours"]
        media_hours[_media_bucket(s["item_type"])] += s["hours"]

        day_key = s["start"].date().isoformat()
        day = daily.setdefault(day_key, {"date": day_key, "hours": 0.0, "transcode_hours": 0.0})
        day["hours"] += s["hours"]
        if s["is_transcode"]:
            day["transcode_hours"] += s["hours"]

        title = by_title.setdefault(s["title"], {"title": s["title"], "hours": 0.0, "plays": 0})
        title["hours"] += s["hours"]

        user = by_user.setdefault(s["user"], {"user_name": s["user"], "hours": 0.0, "plays": 0})
        user["hours"] += s["hours"]

        device = by_device.setdefault(s["client"], {"client": s["client"], "hours": 0.0, "plays": 0})
        device["hours"] += s["hours"]

        if s["is_play"]:
            total_plays += 1
            users_seen.add(s["user"])
            title["plays"] += 1
            user["plays"] += 1
            device["plays"] += 1
            heatmap[(s["start"].weekday(), s["start"].hour)] += 1

            if s["completion_pct"] is not None:
                if s["completion_pct"] >= FINISHED_THRESHOLD_PCT:
                    finished += 1
                else:
                    abandoned += 1

    daily_list = sorted(daily.values(), key=lambda d: d["date"])
    for day in daily_list:
        day["direct_hours"] = round(day["hours"] - day["transcode_hours"], 2)
        day["hours"] = round(day["hours"], 2)
        day["transcode_hours"] = round(day["transcode_hours"], 2)

    completion_total = finished + abandoned
    completion_pct = round(finished / completion_total * 100, 1) if completion_total else None

    return {
        "days": days,
        "summary": {
            "total_plays": total_plays,
            "total_hours": round(total_hours, 1),
            "transcode_hours": round(transcode_hours, 1),
            "direct_hours": round(total_hours - transcode_hours, 1),
            "unique_users": len(users_seen),
            "finished": finished,
            "abandoned": abandoned,
            "completion_pct": completion_pct,
        },
        "daily": daily_list,
        "top_titles": _top(by_title, "title"),
        "top_users": _top(by_user, "user_name"),
        "top_devices": _top(by_device, "client"),
        "heatmap": [
            {"day": day, "hour": hour, "plays": count} for (day, hour), count in heatmap.items()
        ],
        "media_split": [
            {"type": "Movies", "hours": round(media_hours.get("movies", 0.0), 2)},
            {"type": "Shows", "hours": round(media_hours.get("shows", 0.0), 2)},
        ],
    }
