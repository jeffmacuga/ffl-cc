"""Live CBS lineup reads and confirmation-gated lineup updates."""

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from playwright.sync_api import (
    Error as PlaywrightError,
    Request,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


LEAGUE_HOST = "kjfha.football.cbssports.com"
BASE_URL = f"https://{LEAGUE_HOST}"
AUTH_STATE = Path(__file__).resolve().parents[1] / ".auth" / "cbs_state.json"
MY_ROSTER_URL = (
    f"{BASE_URL}/api/league/rosters"
    "?league_id=kjfha&version=3.0&response_format=json"
)
LINEUP_URL = f"{BASE_URL}/api/league/transactions/lineup"


class CBSLineupError(RuntimeError):
    """Raised when CBS state cannot be safely read, changed, or verified."""


def _ensure_chromium_installed(playwright) -> None:
    executable = Path(playwright.chromium.executable_path)
    if executable.is_file():
        return

    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        output = getattr(exc, "stderr", None) or getattr(exc, "stdout", None)
        detail = f" Details: {output.strip()}" if output and output.strip() else ""
        raise CBSLineupError(
            "Playwright Chromium is missing and could not be installed "
            f"automatically.{detail}"
        ) from exc

    if not executable.is_file():
        raise CBSLineupError(
            "Playwright Chromium installation completed, but its browser "
            f"executable was not found at {executable}."
        )


def _launch_browser(playwright):
    _ensure_chromium_installed(playwright)
    try:
        return playwright.chromium.launch(
            headless=True,
            args=["--disable-popup-blocking"],
        )
    except PlaywrightError as exc:
        raise CBSLineupError(
            "Playwright Chromium is installed but could not start. Ensure "
            "the deployment has the Linux libraries listed in the root "
            "`packages.txt`, then redeploy."
        ) from exc


def _roster_fingerprint(team: dict[str, Any], week: str) -> str:
    state = {
        "team_id": str(team["id"]),
        "week": str(week),
        "players": sorted(
            (
                str(player["id"]),
                str(player.get("fullname") or ""),
                str(player.get("position") or ""),
                str(
                    player.get("eligible_positions_display")
                    or player.get("eligible")
                    or ""
                ),
                str(player.get("projected_points") or ""),
                str(player.get("roster_status") or ""),
                str(player.get("roster_pos") or ""),
                str(player.get("is_locked") or ""),
            )
            for player in team.get("players", [])
        ),
    }
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_lineup_payload(
    team_id: str,
    week: str,
    moves: list[dict[str, Any]],
) -> dict[str, Any]:
    active: dict[str, dict[str, str]] = {}
    reserve: dict[str, dict[str, str]] = {}
    for move in moves:
        player_id = str(move["player_id"])
        assignment = str(move["suggested_assignment"])
        slot = str(move["suggested_roster_position"])
        if assignment == "Bench":
            reserve[player_id] = {"pos": slot}
        else:
            active[player_id] = {"pos": slot}

    payload: dict[str, Any] = {"team": str(team_id)}
    if active:
        payload["active"] = active
    if reserve:
        payload["reserve"] = reserve
    payload["point"] = str(week)
    return payload


def _is_locked(value: Any) -> bool:
    if value is True or value == 1:
        return True
    return str(value).strip().lower() in {"1", "true", "yes", "locked"}


def _fetch_live_team(
    page,
    team_id: str | None = None,
    *,
    access_token: str,
) -> tuple[dict[str, Any], str]:
    if not access_token:
        raise CBSLineupError(
            "CBS roster authorization token is missing; "
            "no roster request was sent."
        )

    roster_url = MY_ROSTER_URL
    query = {}
    if team_id is not None:
        query["team_id"] = team_id
    query["access_token"] = access_token
    if query:
        roster_url += f"&{urlencode(query)}"
    result = page.evaluate(
        """async (url) => {
            const response = await fetch(url, {credentials: 'include'});
            return {status: response.status, text: await response.text()};
        }""",
        roster_url,
    )
    if result["status"] != 200:
        raise CBSLineupError(
            f"CBS roster request failed with HTTP {result['status']}."
        )

    try:
        response = json.loads(result["text"])
        body = response.get("body", {})
        if isinstance(body, str):
            body = json.loads(body)
        roster_data = body["rosters"]
        week = str(roster_data["period"])
        teams = roster_data["teams"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise CBSLineupError(
            "CBS returned an unexpected roster response; no changes were sent."
        ) from exc

    if len(teams) != 1:
        raise CBSLineupError(
            "CBS did not identify exactly one roster for the requested team."
        )
    team = teams[0]
    if not team.get("id") or not isinstance(team.get("players"), list):
        raise CBSLineupError(
            "CBS roster data is missing a team ID or player list."
        )
    if team_id is not None and str(team["id"]) != str(team_id):
        raise CBSLineupError(
            "CBS returned a different team than the one selected for preview."
        )
    _merge_page_projections(team, _fetch_page_projections(page))
    return team, week


def _open_cbs_teams_page(
    page,
    team_id: str | None = None,
) -> str:
    roster_page_url = (
        f"{BASE_URL}/teams/{team_id}"
        if team_id is not None
        else f"{BASE_URL}/teams"
    )
    try:
        with page.context.expect_event(
            "request",
            lambda request: _get_access_token(request) is not None,
            timeout=120000,
        ) as token_request:
            page.goto(
                BASE_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
    except PlaywrightTimeoutError as exc:
        raise CBSLineupError(
            "CBS did not issue a fresh roster authorization request within "
            "two minutes. Verify your saved CBS login state and resolve any "
            "CAPTCHA or login challenge, then retry the roster preview."
        ) from exc

    token = _get_access_token(token_request.value)
    if token is None:
        raise CBSLineupError(
            "CBS roster authorization request did not include a token."
        )
    page.goto(
        roster_page_url,
        wait_until="domcontentloaded",
        timeout=60000,
    )
    return token


def _fetch_page_projections(page) -> dict[str, str]:
    result = page.evaluate(
        """() => {
            const normalize = value => value.trim().replace(/\\s+/g, ' ').toUpperCase();
            for (const table of document.querySelectorAll('table')) {
                const rows = [...table.querySelectorAll('tr')];
                let playerIndex = -1;
                let projectionIndex = -1;
                for (const row of rows) {
                    const cells = [...row.querySelectorAll('th, td')];
                    const headers = cells.map(cell => normalize(cell.innerText));
                    playerIndex = headers.findIndex(value => value === 'PLAYERS');
                    projectionIndex = headers.findIndex(value => value.includes('PROJ'));
                    if (playerIndex >= 0 && projectionIndex >= 0) break;
                    playerIndex = -1;
                    projectionIndex = -1;
                }
                if (playerIndex < 0 || projectionIndex < 0) continue;

                const projections = {};
                for (const row of rows) {
                    const cells = [...row.querySelectorAll('th, td')];
                    const link = cells[playerIndex]?.querySelector('a.playerLink');
                    const match = link?.getAttribute('href')?.match(
                        /\\/players\\/playerpage\\/(\\d+)(?:\\/|$)/i
                    );
                    if (match && cells[projectionIndex]) {
                        projections[match[1]] = cells[projectionIndex].innerText.trim();
                    }
                }
                return projections;
            }
            return null;
        }"""
    )
    if not isinstance(result, dict):
        raise CBSLineupError(
            "CBS roster page did not expose its player projection column; "
            "no lineup preview was built."
        )
    return result


def _merge_page_projections(
    team: dict[str, Any],
    page_projections: dict[str, str],
) -> None:
    players = team["players"]
    missing_players = [
        str(player["id"])
        for player in players
        if str(player["id"]) not in page_projections
    ]
    if missing_players:
        raise CBSLineupError(
            "CBS roster page projections could not be matched to every roster "
            "player; no lineup preview was built."
        )

    for player in players:
        value = page_projections[str(player["id"])].replace(",", "").strip()
        if not value:
            player["projected_points"] = None
            continue
        try:
            projection = float(value)
        except ValueError as exc:
            raise CBSLineupError(
                "CBS roster page returned an unrecognized projection value; "
                "no lineup preview was built."
            ) from exc
        if not math.isfinite(projection):
            raise CBSLineupError(
                "CBS roster page returned an invalid projection value; "
                "no lineup preview was built."
            )
        player["projected_points"] = projection


def _normalized_players(team: dict[str, Any]) -> list[dict[str, Any]]:
    players = []
    for player in team["players"]:
        players.append({
            "provider_player_id": str(player["id"]),
            "player_name": player.get("fullname"),
            "position": player.get("position"),
            "eligible_positions": (
                player.get("eligible_positions_display")
                or player.get("eligible")
                or player.get("position")
            ),
            "roster_position": player.get("roster_pos"),
            "roster_status": player.get("roster_status"),
            "projected_points": player.get("projected_points"),
            "average_points": player.get("avg_points"),
            "is_locked": player.get("is_locked"),
        })
    return players


def fetch_my_cbs_roster() -> dict[str, Any]:
    """Read the authenticated user's live CBS roster without changing it."""
    if not AUTH_STATE.is_file():
        raise CBSLineupError(
            f"CBS login state not found: {AUTH_STATE}. "
            "Run `python archive\\legacy-cbs\\cbs_session.py` first."
        )

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        try:
            context = browser.new_context(storage_state=str(AUTH_STATE))
            page = context.new_page()
            access_token = _open_cbs_teams_page(page)
            team, week = _fetch_live_team(page, access_token=access_token)
            return {
                "team_id": str(team["id"]),
                "team_name": str(team.get("name") or team["id"]),
                "week": week,
                "lineup_status": team.get("lineup_status"),
                "players": _normalized_players(team),
                "fingerprint": _roster_fingerprint(team, week),
            }
        finally:
            browser.close()


def fetch_cbs_team_roster(team_id: str) -> dict[str, Any]:
    """Read another CBS team for preview only; this function never submits changes."""
    if not str(team_id).isdigit():
        raise CBSLineupError("CBS team ID must be numeric.")
    if not AUTH_STATE.is_file():
        raise CBSLineupError(
            f"CBS login state not found: {AUTH_STATE}. "
            "Run `python archive\\legacy-cbs\\cbs_session.py` first."
        )

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        try:
            context = browser.new_context(storage_state=str(AUTH_STATE))
            page = context.new_page()
            access_token = _open_cbs_teams_page(page, team_id)
            team, week = _fetch_live_team(
                page,
                str(team_id),
                access_token=access_token,
            )
            return {
                "team_id": str(team["id"]),
                "team_name": str(team.get("name") or team["id"]),
                "week": week,
                "lineup_status": team.get("lineup_status"),
                "players": _normalized_players(team),
                "fingerprint": _roster_fingerprint(team, week),
            }
        finally:
            browser.close()


def _get_access_token(request: Request) -> str | None:
    parts = urlsplit(request.url)
    if parts.hostname != LEAGUE_HOST or "/api/league/feed" not in parts.path:
        return None
    return next(
        (
            value
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key == "access_token" and value
        ),
        None,
    )


def _verify_assignments(
    team: dict[str, Any],
    moves: list[dict[str, Any]],
) -> None:
    players_by_id = {str(player["id"]): player for player in team["players"]}
    for move in moves:
        player_id = str(move["player_id"])
        player = players_by_id.get(player_id)
        if player is None:
            raise CBSLineupError(
                f"CBS verification failed: player {move['player']} is no longer "
                "on your roster."
            )

        expected_status = (
            "RS" if move["suggested_assignment"] == "Bench" else "A"
        )
        expected_position = str(move["suggested_roster_position"])
        actual_status = str(player.get("roster_status") or "").upper()
        actual_position = str(player.get("roster_pos") or "")
        if (
            actual_status != expected_status
            or actual_position != expected_position
        ):
            raise CBSLineupError(
                f"CBS did not confirm the requested assignment for "
                f"{move['player']}; actual status/slot is "
                f"{actual_status or 'unknown'}/{actual_position or 'unknown'}."
            )


def apply_confirmed_lineup(
    *,
    expected_fingerprint: str,
    team_id: str,
    week: str,
    moves: list[dict[str, Any]],
) -> None:
    """Submit only confirmed moves after a fresh-state and lock check."""
    if not moves:
        raise CBSLineupError("There are no lineup changes to submit.")
    if not AUTH_STATE.is_file():
        raise CBSLineupError(
            f"CBS login state not found: {AUTH_STATE}. "
            "Run `python archive\\legacy-cbs\\cbs_session.py` first."
        )

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        try:
            context = browser.new_context(storage_state=str(AUTH_STATE))
            page = context.new_page()
            access_token = _open_cbs_teams_page(page)
            team, current_week = _fetch_live_team(
                page,
                access_token=access_token,
            )

            if str(team["id"]) != str(team_id) or current_week != str(week):
                raise CBSLineupError(
                    "Your CBS team or matchup week changed since the preview. "
                    "Refresh the preview before submitting."
                )
            if _roster_fingerprint(team, current_week) != expected_fingerprint:
                raise CBSLineupError(
                    "Your CBS roster or lineup changed since the preview. "
                    "Refresh the preview before submitting."
                )

            player_by_id = {
                str(player["id"]): player for player in team["players"]
            }
            for move in moves:
                player = player_by_id.get(str(move["player_id"]))
                if player is None:
                    raise CBSLineupError(
                        f"{move['player']} is no longer on your CBS roster."
                    )
                if player.get("is_locked") is None:
                    raise CBSLineupError(
                        "CBS did not provide player lock status; no changes were sent."
                    )
                if _is_locked(player["is_locked"]):
                    raise CBSLineupError(
                        f"{move['player']} is locked in CBS; no changes were sent."
                    )

            form_data = {
                "payload": json.dumps(
                    build_lineup_payload(team_id, week, moves),
                    separators=(",", ":"),
                ),
                "access_token": access_token,
                "version": "2.0",
                "resultFormat": "json",
                "responseFormat": "json",
            }
            result = page.evaluate(
                """async ({url, form}) => {
                    const response = await fetch(url, {
                        method: 'PUT',
                        credentials: 'include',
                        headers: {
                            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            'x-requested-with': 'XMLHttpRequest',
                            'accept': 'application/json, text/javascript, */*; q=0.01'
                        },
                        body: new URLSearchParams(form).toString()
                    });
                    return {status: response.status, text: await response.text()};
                }""",
                {"url": LINEUP_URL, "form": form_data},
            )
            verified_team, verified_week = _fetch_live_team(
                page,
                access_token=access_token,
            )
            if str(verified_team["id"]) != str(team_id) or verified_week != str(week):
                raise CBSLineupError(
                    "CBS lineup update response was received, but the roster "
                    "could not be verified for the expected team and week."
                )
            try:
                _verify_assignments(verified_team, moves)
            except CBSLineupError as exc:
                raise CBSLineupError(
                    f"CBS lineup update returned HTTP {result['status']}, but "
                    f"the requested lineup could not be verified: {exc}"
                ) from exc
            if result["status"] < 200 or result["status"] >= 300:
                raise CBSLineupError(
                    f"CBS returned HTTP {result['status']}, but the requested "
                    "assignments are present in the verified roster."
                )
        finally:
            browser.close()
