import hashlib
import json
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import Request, Response, sync_playwright


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

LEAGUE_HOST = "kjfha.football.cbssports.com"
START_URL = f"https://{LEAGUE_HOST}/"
AUTH_STATE = Path(".auth/cbs_state.json")
OUTPUT = Path("discovery_output")
CAPTURE_SECONDS = 120
TOKEN_WAIT_SECONDS = 15

# Candidate only; CBS may use another endpoint discovered during capture.
TEST_ENDPOINT = "/api/league/rosters?kjfha&version=3.0&response_format=json"

    "https://kjfha.football.cbssports.com/api/league/rosters?league_id=kjfha&team_id=15&version=3.0&response_format=json"


SENSITIVE_PARAMS = {
    "access_token",
    "api_key",
    "authorization",
    "auth",
    "key",
    "session",
    "sessionid",
    "token",
}

SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
}

OUTPUT.mkdir(parents=True, exist_ok=True)
captured_authorization = None


# -------------------------------------------------------------------
# Redaction and output helpers
# -------------------------------------------------------------------

def sanitize_url(url):
    """Redact sensitive URL query parameters before writing URLs to disk."""
    parts = urlsplit(url)
    safe_query = []

    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        safe_value = "[REDACTED]" if key.lower() in SENSITIVE_PARAMS else value
        safe_query.append((key, safe_value))

    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(safe_query), parts.fragment)
    )


def sanitize_headers(headers):
    return {
        key: "[REDACTED]" if key.lower() in SENSITIVE_HEADERS else value
        for key, value in headers.items()
    }


def output_name(url):
    parts = urlsplit(url)
    stem = parts.path.strip("/").replace("/", "_") or "root"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return f"{stem[:100]}_{digest}.json"


def looks_like_roster_payload(payload):
    """Return True when JSON appears to contain CBS league roster data."""
    if not isinstance(payload, dict):
        return False

    body = payload.get("body")
    if isinstance(body, dict):
        rosters = body.get("rosters")
        if isinstance(rosters, dict) and isinstance(rosters.get("teams"), list):
            return True

    return "roster" in json.dumps(payload, ensure_ascii=False).lower()


def save_discovery(request, response, payload):
    safe_url = sanitize_url(response.url)
    record = {
        "request": {
            "method": request.method,
            "url": safe_url,
            "headers": sanitize_headers(request.headers),
        },
        "response": {
            "status": response.status,
            "url": safe_url,
            "headers": sanitize_headers(response.headers),
        },
        "payload": payload,
    }

    destination = OUTPUT / output_name(response.url)
    destination.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[SAVED] {destination}")

    if looks_like_roster_payload(payload):
        roster_file = OUTPUT / "cbs_rosters.json"
        roster_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        teams = payload.get("body", {}).get("rosters", {}).get("teams", [])
        player_count = sum(len(team.get("players", [])) for team in teams)
        print(f"[ROSTER PAYLOAD] {len(teams)} teams, {player_count} players")
        print(f"[SAVED] {roster_file}")


# -------------------------------------------------------------------
# Network handlers
# -------------------------------------------------------------------

def capture_token(request: Request):
    """Keep authorization in memory for the optional endpoint test."""
    global captured_authorization

    authorization = request.headers.get("authorization")
    if authorization and captured_authorization is None:
        captured_authorization = authorization
        print("[AUTH] Authorization header captured in memory")


def capture_response(response: Response):
    try:
        parsed = urlsplit(response.url)
        if parsed.hostname != LEAGUE_HOST:
            return

        content_type = response.headers.get("content-type", "").lower()
        if "json" not in content_type:
            return

        payload = response.json()
        save_discovery(response.request, response, payload)
    except Exception as exc:
        print(f"[SKIP] Could not process {sanitize_url(response.url)}: {exc}")

def capture(response):
    url = response.url

    if "league" in url or "roster" in url:
        print(url)
# -------------------------------------------------------------------
# Candidate endpoint test
# -------------------------------------------------------------------

def test_rosters_endpoint(page):
    url = f"https://{LEAGUE_HOST}{TEST_ENDPOINT}"
    headers = {}
    if captured_authorization:
        headers["authorization"] = captured_authorization

    print(f"[ROSTERS TEST] GET {sanitize_url(url)}")
    try:
        result = page.evaluate(
            """async ({url, headers}) => {
                const response = await fetch(url, {
                    method: 'GET',
                    credentials: 'include',
                    headers
                });
                const text = await response.text();
                return {
                    status: response.status,
                    contentType: response.headers.get('content-type') || '',
                    text
                };
            }""",
            {"url": url, "headers": headers},
        )

        print(f"[ROSTERS TEST] Status {result['status']}")
        try:
            payload = json.loads(result["text"])
        except json.JSONDecodeError:
            print("[ROSTERS TEST] Response was not JSON")
            return

        destination = OUTPUT / "candidate_rosters_response.json"
        destination.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[SAVED] {destination}")

        if looks_like_roster_payload(payload):
            teams = payload.get("body", {}).get("rosters", {}).get("teams", [])
            player_count = sum(len(team.get("players", [])) for team in teams)
            print(f"[ROSTERS TEST] {len(teams)} teams, {player_count} players")
    except Exception as exc:
        print(f"[ROSTERS TEST] Failed: {exc}")


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

from playwright.sync_api import sync_playwright

AUTH_STATE = ".auth/cbs_state.json"

    def main():

        with sync_playwright() as pw:

            browser = pw.chromium.launch(
                headless=False
            )

            context = browser.new_context(
                storage_state=AUTH_STATE
            )

            page = context.new_page()

            def capture(response):

                url = response.url.lower()

                if (
                    "roster" in url
                    or "team" in url
                    or "league" in url
                    or "player" in url
                ):
                    print()
                    print("=" * 80)
                    print(response.status)
                    print(response.url)
                    print("=" * 80)

            page.on("response", capture)

            page.goto(
                "https://kjfha.football.cbssports.com/teams/roster-grid",
                wait_until="networkidle"
            )

            print(
                "\nBrowse around the site."
                "\nOpen multiple team roster pages."
                "\nPress Enter when done."
            )

            input()

            browser.close()


    if __name__ == "__main__":
        main()