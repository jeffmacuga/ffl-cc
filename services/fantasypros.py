"""FantasyPros weekly projections for CBS lineup decision support."""

import json
import math
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import FANTASYPROS_API_KEY


API_BASE_URL = "https://api.fantasypros.com/public/v2/json/nfl"
PROJECTION_BATCH_LIMIT = 500
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
    query = urlencode({
        "position": position,
        "week": week,
        "limit": PROJECTION_BATCH_LIMIT,
    })
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
    try:
        expected_count = int(payload.get("count", len(payload["players"])))
        returned_limit = int(payload.get("limit", PROJECTION_BATCH_LIMIT))
    except (TypeError, ValueError) as exc:
        raise FantasyProsAPIError(
            f"FantasyPros returned invalid pagination metadata for "
            f"{position} projections."
        ) from exc
    if expected_count > len(payload["players"]) and (
        returned_limit < PROJECTION_BATCH_LIMIT
        or len(payload["players"])
        < min(expected_count, PROJECTION_BATCH_LIMIT)
    ):
        raise FantasyProsAPIError(
            f"FantasyPros returned only {len(payload['players'])} of "
            f"{expected_count} {position} projections despite a requested "
            f"limit of {PROJECTION_BATCH_LIMIT}; its pagination parameters "
            "must be configured before lineup advice can be complete."
        )
    return payload


def _fetch_json(url, api_key, description):
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
            f"FantasyPros returned HTTP {exc.code} for {description}."
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise FantasyProsAPIError(
            f"FantasyPros {description} could not be reached."
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FantasyProsAPIError(
            f"FantasyPros returned invalid JSON for {description}."
        ) from exc
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


def fetch_consensus_rankings(
    roster,
    season,
    scoring="PPR",
    api_key=None,
):
    """Fetch consensus overall rankings for rostered player positions."""
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

    positions = sorted({
        _projection_position(player.get("position"))
        for player in roster
    })
    records = []
    for position in positions:
        query = urlencode({
            "position": position,
            "scoring": normalized_scoring,
            "experts": "show",
        })
        url = f"{API_BASE_URL}/{season}/consensus-rankings?{query}"
        payload = _fetch_json(
            url,
            key,
            f"{position} consensus rankings",
        )
        if not isinstance(payload, dict) or not isinstance(
            payload.get("players"), list
        ):
            raise FantasyProsAPIError(
                f"FantasyPros returned an unexpected {position} consensus "
                "rankings shape."
            )
        if payload.get("year") and str(payload["year"]) != str(season):
            raise FantasyProsAPIError(
                f"FantasyPros returned consensus rankings for season "
                f"{payload['year']}, not {season}."
            )
        records.extend(
            player
            for player in payload["players"]
            if isinstance(player, dict)
        )

    by_cbs_id = {}
    by_name_team = {}
    for record in records:
        cbs_id = str(record.get("cbs_player_id") or "").strip()
        fantasypros_id = str(record.get("player_id") or "").strip()
        player_name = record.get("player_name")
        team = str(record.get("player_team_id") or "").strip().upper()
        rank = record.get("rank_ecr")
        try:
            rank = float(rank)
        except (TypeError, ValueError):
            rank = None
        if rank is None or not math.isfinite(rank):
            continue
        ranking = {
            "rank": rank,
            "fantasypros_player_id": fantasypros_id,
            "name": player_name,
        }
        if cbs_id:
            by_cbs_id[cbs_id] = ranking
        if player_name:
            by_name_team.setdefault(
                (_name_key(player_name), team),
                [],
            ).append(ranking)

    enriched_roster = []
    missing_rankings = []
    for player in roster:
        cbs_id = str(
            player.get("provider_player_id") or player.get("id") or ""
        ).strip()
        name = player.get("fullname") or player.get("player_name")
        team = str(player.get("pro_team") or "").strip().upper()
        ranking = by_cbs_id.get(cbs_id)
        if ranking is None:
            candidates = by_name_team.get((_name_key(name), team), [])
            if len(candidates) == 1:
                ranking = candidates[0]

        enriched_player = dict(player)
        enriched_player["consensus_rank"] = (
            ranking["rank"] if ranking else None
        )
        enriched_player["fantasypros_player_id"] = (
            ranking["fantasypros_player_id"] if ranking else None
        )
        if ranking is None:
            missing_rankings.append(str(name or "Unknown player"))
        enriched_roster.append(enriched_player)

    return {
        "roster": enriched_roster,
        "missing_players": missing_rankings,
        "records": records,
    }


def fetch_injury_news(roster, fantasypros_player_ids, api_key=None):
    """Fetch recent FantasyPros injury news associated with rostered players."""
    key = FANTASYPROS_API_KEY if api_key is None else api_key
    if not key:
        raise FantasyProsAPIError(
            "FantasyPros API key is not configured. Set "
            "FANTASYPROS_API_KEY in Streamlit secrets or the environment."
        )
    query = urlencode({"limit": 100, "category": "injury"})
    url = f"{API_BASE_URL}/news?{query}"
    payload = _fetch_json(url, key, "NFL injury news")
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise FantasyProsAPIError(
            "FantasyPros returned an unexpected NFL news response shape."
        )
    try:
        count = int(payload.get("count", len(payload["items"])))
    except (TypeError, ValueError) as exc:
        raise FantasyProsAPIError(
            "FantasyPros returned invalid NFL news count metadata."
        ) from exc
    if count > len(payload["items"]):
        raise FantasyProsAPIError(
            f"FantasyPros returned only {len(payload['items'])} of "
            f"{count} NFL injury news items; increase the news limit before "
            "relying on a complete injury feed."
        )

    roster_ids_by_player_id = {
        str(fantasypros_id): str(
            player.get("provider_player_id") or player.get("id") or ""
        )
        for player in roster
        if (fantasypros_id := fantasypros_player_ids.get(
            str(player.get("provider_player_id") or player.get("id") or "")
        ))
    }
    matched_news = []
    for item in payload["items"]:
        if not isinstance(item, dict):
            continue
        player_id = str(item.get("player_id") or "").strip()
        roster_id = roster_ids_by_player_id.get(player_id)
        if roster_id is None:
            continue
        matched_news.append({
            "player_id": roster_id,
            "title": str(item.get("title") or ""),
            "description": str(item.get("desc") or ""),
            "impact": str(item.get("impact") or ""),
            "categories": item.get("categories") or [],
            "created": str(item.get("created_formated") or item.get("created") or ""),
            "link": str(item.get("link") or ""),
        })
    return matched_news
