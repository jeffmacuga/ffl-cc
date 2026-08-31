import json
import sqlite3
from pathlib import Path

from playwright.sync_api import sync_playwright

from cbs_normalize import (
    normalize_cbs_rosters,
    upsert_cbs_data,
)

DB_PATH = r"C:\Users\User\source\repos\ffl-cc\fantasy.db"

AUTH_STATE = Path(".auth/cbs_state.json")

TEAMS_URL = (
    "https://kjfha.football.cbssports.com"
    "/api/league/teams"
    "?league_id=kjfha"
    "&version=3.0"
    "&response_format=json"
)

ROSTER_URL_TEMPLATE = (
    "https://kjfha.football.cbssports.com"
    "/api/league/rosters"
    "?league_id=kjfha"
    "&team_id={team_id}"
    "&version=3.0"
    "&response_format=json"
)

STANDINGS_URL = (
    "https://kjfha.football.cbssports.com"
    "/api/league/standings/overall"
    "?league_id=kjfha"
    "&version=3.0"
    "&response_format=json"
)


def fetch_json(page, url):

    print("REQUESTING:", url)

    result = page.evaluate(
        """
        async (url) => {
            const response = await fetch(
                url,
                { credentials: 'include' }
            );

            return {
                status: response.status,
                body: await response.text()
            };
        }
        """,
        url,
    )

    print("STATUS:", result["status"])

    if result["status"] != 200:
        raise RuntimeError(
            f"Request failed: {url}\n"
            f"Status: {result['status']}\n"
            f"{result['body'][:1000]}"
        )

    return json.loads(result["body"])

def fetch_and_store_cbs_standings(page, conn):
    print("REQUESTING CBS STANDINGS:", STANDINGS_URL)
    standings_data = fetch_json(page, STANDINGS_URL)
    body = standings_data["body"]
    if isinstance(body, str):
        body = json.loads(body)

    # Extract teams from divisions in overall_standings
    standings = []
    overall = body.get("overall_standings", {})
    for division in overall.get("divisions", []):
        for team in division.get("teams", []):
            standings.append({
                "team_id": str(team["id"]),
                "team_name": team["name"],
                "wins": team["wins"],
                "losses": team["losses"],
                "ties": team.get("ties", 0),
                "points_for": team.get("points_scored", 0)
            })

    print(f"Fetched {len(standings)} standings rows")

    # Create table if not exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cbs_standings (
            team_id TEXT PRIMARY KEY,
            team_name TEXT,
            wins INTEGER,
            losses INTEGER,
            ties INTEGER,
            points_for REAL
        )
    """)
    # Upsert standings
    for entry in standings:
        conn.execute("""
            INSERT INTO cbs_standings (team_id, team_name, wins, losses, ties, points_for)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id) DO UPDATE SET
                team_name=excluded.team_name,
                wins=excluded.wins,
                losses=excluded.losses,
                ties=excluded.ties,
                points_for=excluded.points_for
        """, (
            entry["team_id"],
            entry["team_name"],
            entry["wins"],
            entry["losses"],
            entry.get("ties", 0),
            entry["points_for"]
        ))
    conn.commit()
    print("CBS standings updated.")


def main():

    print("RUNNING ALL-TEAM IMPORT")

    with sync_playwright() as pw:

        browser = pw.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            storage_state=str(AUTH_STATE)
        )

        page = context.new_page()

        page.goto(
            "https://kjfha.football.cbssports.com/teams/roster-grid",
            wait_until="domcontentloaded",
            timeout=60000
        )

        print("URL:", page.url)
        print("TITLE:", page.title())

        print("Loading teams...")

        teams_data = fetch_json(
            page,
            TEAMS_URL
        )

        print(type(teams_data))
        print(teams_data.keys())

        body = teams_data["body"]

        if isinstance(body, str):
            body = json.loads(body)

        team_ids = [
            team["id"]
            for team in body["teams"]
        ]

        print(
            f"Found {len(team_ids)} teams"
        )

        print(team_ids)

        all_teams = []
        all_players = []

        for team_id in team_ids:

            roster_url = (
                ROSTER_URL_TEMPLATE.format(
                    team_id=team_id
                )
            )

            print(
                f"Downloading team {team_id}"
            )

            roster_data = fetch_json(
                page,
                roster_url
            )

            teams, players = (
                normalize_cbs_rosters(
                    roster_data
                )
            )

            all_teams.extend(teams)
            all_players.extend(players)
        
        with sqlite3.connect(DB_PATH) as conn:

            conn.execute(
                "PRAGMA foreign_keys = ON"
            )

            upsert_cbs_data(
                conn,
                all_teams,
                all_players
            )
       
            fetch_and_store_cbs_standings(page, conn)

        browser.close()

    print()
    print(
        f"Total teams: "
        f"{len(all_teams)}"
    )

    print(
        f"Total players: "
        f"{len(all_players)}"
    )

    print(
        "Import complete."
    )


if __name__ == "__main__":
    main()