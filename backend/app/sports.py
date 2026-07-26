from datetime import datetime, timedelta, timezone

import httpx

CLEVELAND_ABBR = "CLE"

LEAGUES = {
    "browns": "football/nfl",
    "cavaliers": "basketball/nba",
    "guardians": "baseball/mlb",
}


async def _fetch_events(sport_path: str) -> list[dict]:
    start = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y%m%d")
    end = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params={"dates": f"{start}-{end}"})
        response.raise_for_status()
        return response.json().get("events", [])


def _summarize(event: dict) -> dict | None:
    competition = (event.get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []

    cleveland = next(
        (c for c in competitors if (c.get("team") or {}).get("abbreviation") == CLEVELAND_ABBR),
        None,
    )
    if not cleveland:
        return None

    opponent = next((c for c in competitors if c is not cleveland), {})
    status_type = (event.get("status") or {}).get("type") or {}

    return {
        "state": status_type.get("state"),
        "status_detail": status_type.get("shortDetail"),
        "start_time": event.get("date"),
        "cleveland_team": (cleveland.get("team") or {}).get("displayName"),
        "cleveland_score": cleveland.get("score"),
        "cleveland_logo": (cleveland.get("team") or {}).get("logo"),
        "cleveland_is_home": cleveland.get("homeAway") == "home",
        "opponent_team": (opponent.get("team") or {}).get("displayName"),
        "opponent_score": opponent.get("score"),
        "opponent_logo": (opponent.get("team") or {}).get("logo"),
    }


def _pick_best(events: list[dict]) -> dict | None:
    summaries = [s for s in (_summarize(e) for e in events) if s]
    if not summaries:
        return None

    live = [s for s in summaries if s["state"] == "in"]
    if live:
        return live[0]

    finals = sorted(
        (s for s in summaries if s["state"] == "post"),
        key=lambda s: s["start_time"] or "",
        reverse=True,
    )
    if finals:
        return finals[0]

    upcoming = sorted(
        (s for s in summaries if s["state"] == "pre"),
        key=lambda s: s["start_time"] or "",
    )
    return upcoming[0] if upcoming else None


async def cleveland_scores() -> dict:
    results: dict[str, dict | None] = {}
    for key, sport_path in LEAGUES.items():
        try:
            events = await _fetch_events(sport_path)
            results[key] = _pick_best(events)
        except Exception:
            results[key] = None
    return results
