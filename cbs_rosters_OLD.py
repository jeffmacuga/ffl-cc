# cbs_rosters.py

import json
import sqlite3
from pathlib import Path
from playwright.sync_api import Request, Response, sync_playwright
from cbs_normalize import (
    normalize_cbs_rosters,
    upsert_cbs_data,
)

DB_PATH = r"C:\Users\User\source\ffl-mgr\fantasy.db"

# Replace with the actual endpoint discovered from Playwright
ROSTER_URL = (
    "https://kjfha.football.cbssports.com/api/league/rosters?league_id=kjfha&team_id=15&version=3.0&response_format=json"
)

# Replace with your real auth values
HEADERS = {
    "Accept": "application/json",
    # "Authorization": "Bearer ...",
}
def download_rosters():

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)

        context = browser.new_context(
            storage_state=".auth/cbs_state.json"
        )
        cookies = context.cookies()

        print("\nCookies loaded:")
        for cookie in cookies:
            print(cookie["name"]
        )

        page = context.new_page()

        page.goto(
            ROSTER_URL,
            wait_until="networkidle"
        )
        print("\n=== PAGE DEBUG ===")
        print("URL:", page.url)
        print("TITLE", page.title())

        content = page.content()

        if "sign in" in content.lower():
            print("NOT LOGGED IN")
        else:
            print("LOGIN APPEARS VALID")

        result = page.evaluate(
            """
            async (url) => {
                const r = await fetch(url, {
                    credentials: 'include'
                });

                return {
                    status: r.status,
                    body: await r.text()
                };
            }
            """,
        ROSTER_URL
    )

    print(result["status"])
    print(result["body"][:5000])

    if result["status"] != 200:
        raise RuntimeError(
        f"CBS API returned {result['status']}"
        )
    
    return json.loads(result["body"])


def main():
    data = download_rosters()

    print(json.dumps(data, indent=2)[:2000])

    teams, players = normalize_cbs_rosters(data)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        upsert_cbs_data(conn, teams, players)

    print(
        f"Imported {len(teams)} teams "
        f"and {len(players)} players"
    )


if __name__ == "__main__":
    main()