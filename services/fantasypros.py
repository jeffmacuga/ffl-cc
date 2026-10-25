"""FantasyPros weekly projections for CBS lineup decision support."""

import json
import math
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import FANTASYPROS_API_KEY


API_BASE_URL = "https://api.fantasypros.com/public/v2/json/nfl"
SCORING_FIELDS = {
    "PPR": "points_ppr",
    "HALF-PPR": "points_half",
    "STANDARD": "points",
}
POSITION_ENDPOINTS = {
    "QB": "QB",
    "RB": "RB",
    "WR": "WR",
    "TE": "TE",
    "K": "K",
    "DST": "DST",
    "DEF": "DST",
    "D/ST": "DST",
}


class FantasyProsAPIError(RuntimeError):
    """Raised when FantasyPros projections cannot be safely loaded."""


def _name_key(value):
    normalized = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _projection_position(value):
    position = str(value or "").strip().upper()
    try:
        return POSITION_ENDPOINTS[position]
    except KeyError as exc:
        raise FantasyProsAPIError(
            f"FantasyPros projections do not support CBS position {position!r}."
        ) from exc


def _fetch_position_payload(season, week, position, api_key):
    query = urlencode({"position": position, "week": week})
    url = f"{API_BASE_URL}/{season}/projections?{query}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "x-api-key": api_key,
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise FantasyProsAPIError(
            f"FantasyPros returned HTTP {exc.code} for {position} projections."
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise FantasyProsAPIError(
            f"FantasyPros {position} projections could not be reached."
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FantasyProsAPIError(
            f"FantasyPros returned invalid JSON for {position} projections."
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("players"), list):
        raise FantasyProsAPIError(
            f"FantasyPros returned an unexpected {position} projections shape."
        )
    if payload.get("season") and str(payload["season"]) != str(season):
        raise FantasyProsAPIError(
            f"FantasyPros returned projections for season {payload['season']}, "
            f"not {season}."
        )
    if payload.get("week") and str(payload["week"]) != str(week):
        raise FantasyProsAPIError(
            f"FantasyPros returned projections for week {payload['week']}, "
            f"not {week}."
        )
    return payload


def _scoring_projection(player, scoring):
    stats = player.get("stats")
    if not isinstance(stats, dict):
        return None
    value = stats.get(SCORING_FIELDS[scoring])
    try:
        projection = float(value)
    except (TypeError, ValueError):
        return None
    return projection if math.isfinite(projection) else None


def fetch_weekly_projections(
    roster,
    season,
    week,
    scoring="PPR",
    api_key=None,
):
    """Fetch positional projections and match them to CBS rostered players."""
    key = FANTASYPROS_API_KEY if api_key is None else api_key
    if not key:
        raise FantasyProsAPIError(
            "FantasyPros API key is not configured. Set "
            "FANTASYPROS_API_KEY in Streamlit secrets or the environment."
        )

    normalized_scoring = str(scoring).strip().upper()
    if normalized_scoring not in SCORING_FIELDS:
        raise FantasyProsAPIError(
            f"Unsupported FantasyPros scoring format: {scoring!r}."
        )

    api_positions = sorted({
        _projection_position(player.get("position"))
        for player in roster
    })
    projections_by_name = {}
    for position in api_positions:
        payload = _fetch_position_payload(season, week, position, key)
        for player in payload["players"]:
            if not isinstance(player, dict):
                continue
            name_key = _name_key(player.get("name"))
            projection = _scoring_projection(player, normalized_scoring)
            if not name_key or projection is None:
                continue
            candidate = {
                "team": str(player.get("team_id") or "").strip().upper(),
                "projection": projection,
            }
            candidates = projections_by_name.setdefault(name_key, [])
            if candidate not in candidates:
                candidates.append(candidate)

    enriched_roster = []
    missing_players = []
    for player in roster:
        name = player.get("fullname") or player.get("player_name")
        name_key = _name_key(name)
        candidates = projections_by_name.get(name_key, [])
        team = str(player.get("pro_team") or "").strip().upper()
        matching_team = [
            candidate for candidate in candidates
            if team and candidate["team"] == team
        ]
        if len(matching_team) == 1:
            projection = matching_team[0]["projection"]
        elif len(candidates) == 1:
            projection = candidates[0]["projection"]
        else:
            projection = None

        enriched_player = dict(player)
        enriched_player["cbs_projected_points"] = player.get("projected_points")
        enriched_player["fantasypros_projected_points"] = projection
        if projection is None:
            missing_players.append(str(name or "Unknown player"))
        else:
            enriched_player["projected_points"] = projection
        enriched_roster.append(enriched_player)

    return {
        "roster": enriched_roster,
        "missing_players": missing_players,
        "scoring": normalized_scoring,
    }
