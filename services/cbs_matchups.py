"""Read weekly CBS fantasy matchups from team schedule pages."""

import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


CBS_BASE_URL = "https://kjfha.football.cbssports.com"
CBS_AUTH_STATE = (
    Path(__file__).resolve().parents[1] / ".auth" / "cbs_state.json"
)
SCORE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)")


class CBSMatchupError(RuntimeError):
    """Raised when CBS matchup data cannot be read or parsed."""


def _read_schedule_rows(page):
    rows = page.locator("table").evaluate_all(
        """tables => {
            for (const table of tables) {
                const headerRow = [...table.querySelectorAll("tr")]
                    .find(row => row.classList.contains("label"));
                if (!headerRow) continue;
                const headers = [...headerRow.querySelectorAll("th")]
                    .map(cell => cell.innerText.trim().toUpperCase());
                const periodIndex = headers.indexOf("PERIOD");
                const opponentIndex = headers.indexOf("OPPONENT");
                const resultIndex = headers.indexOf("RESULT");
                if (periodIndex < 0 || opponentIndex < 0 || resultIndex < 0) {
                    continue;
                }
                return [...table.querySelectorAll("tr.row1, tr.row2")]
                    .map(row => {
                        const cells = [...row.querySelectorAll("td")];
                        const opponentCell = cells[opponentIndex];
                        const teamLink = opponentCell?.querySelector(
                            'a[href*="/teams/"]'
                        );
                        const match = teamLink?.getAttribute("href")?.match(
                            /\\/teams\\/(\\d+)(?:\\/|$)/
                        );
                        return {
                            week: cells[periodIndex]?.innerText.trim(),
                            opponent_id: match?.[1] ?? null,
                            opponent: opponentCell?.innerText.trim() ?? "",
                            result: cells[resultIndex]?.innerText.trim() ?? "",
                        };
                    });
            }
            return null;
        }"""
    )
    if not isinstance(rows, list):
        raise CBSMatchupError(
            "CBS did not provide a recognizable team schedule."
        )
    return rows


def _result_scores(result):
    match = SCORE_PATTERN.search(result or "")
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def build_cbs_matchups(team_names, team_schedules):
    """Combine each team's schedule into one row per weekly matchup."""
    matchups = {}
    for schedule in team_schedules:
        team_id = str(schedule["team_id"])
        team_name = team_names[team_id]
        for item in schedule["rows"]:
            try:
                week = int(item["week"])
            except (TypeError, ValueError) as exc:
                raise CBSMatchupError(
                    "CBS returned a schedule row with an invalid week."
                ) from exc

            opponent_id = item.get("opponent_id")
            if opponent_id is not None:
                opponent_id = str(opponent_id)
                opponent_name = team_names.get(
                    opponent_id,
                    str(item.get("opponent") or opponent_id),
                )
                pair_ids = tuple(sorted((team_id, opponent_id)))
                key = (week, *pair_ids)
                team_a_name = team_names.get(
                    pair_ids[0],
                    team_name if pair_ids[0] == team_id else opponent_name,
                )
                team_b_name = team_names.get(
                    pair_ids[1],
                    team_name if pair_ids[1] == team_id else opponent_name,
                )
            else:
                opponent_name = str(item.get("opponent") or "BYE")
                key = (week, team_id, opponent_name)
                team_a_name = team_name
                team_b_name = opponent_name

            matchup = matchups.setdefault(
                key,
                {
                    "Week": week,
                    "Team A": team_a_name,
                    "Team B": team_b_name,
                    "Team A Score": None,
                    "Team B Score": None,
                },
            )
            scores = _result_scores(item.get("result", ""))
            if scores is None:
                continue

            if team_id == key[1]:
                matchup["Team A Score"], matchup["Team B Score"] = scores
            else:
                matchup["Team B Score"], matchup["Team A Score"] = scores

    return sorted(
        matchups.values(),
        key=lambda matchup: (matchup["Week"], matchup["Team A"]),
    )


def fetch_cbs_weekly_matchups(teams, season=None):
    """Fetch and combine the current CBS league's team schedule pages."""
    if not CBS_AUTH_STATE.is_file():
        raise CBSMatchupError(
            f"CBS login state not found: {CBS_AUTH_STATE}. "
            "Run `python archive/legacy-cbs/cbs_session.py` first."
        )
    if not teams:
        raise CBSMatchupError("No CBS teams are available.")

    team_names = {}
    for team in teams:
        team_id = str(team["provider_team_id"])
        if not team_id.isdigit():
            raise CBSMatchupError("CBS team IDs must be numeric.")
        team_names[team_id] = str(team["team_name"])

    season = season or datetime.now().year
    team_schedules = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-popup-blocking"],
            )
            try:
                context = browser.new_context(
                    storage_state=str(CBS_AUTH_STATE)
                )
                page = context.new_page()
                for team_id in team_names:
                    response = page.goto(
                        f"{CBS_BASE_URL}/schedule/team/{team_id}/{season}",
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                    if response is None or response.status != 200:
                        status = response.status if response is not None else (
                            "no response"
                        )
                        raise CBSMatchupError(
                            "CBS schedule request failed with "
                            f"HTTP {status} for team {team_id}."
                        )
                    team_schedules.append({
                        "team_id": team_id,
                        "rows": _read_schedule_rows(page),
                    })
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise CBSMatchupError(
            "CBS did not load a team schedule before the request timed out."
        ) from exc
    except PlaywrightError as exc:
        raise CBSMatchupError(
            "CBS team schedules could not be loaded. Verify the saved CBS "
            "login state and that Playwright Chromium is available."
        ) from exc

    return build_cbs_matchups(team_names, team_schedules)
