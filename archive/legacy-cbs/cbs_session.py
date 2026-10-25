from pathlib import Path
from playwright.sync_api import sync_playwright

LEAGUE_URL = "https://kjfha.football.cbssports.com/"
AUTH = Path(__file__).resolve().parents[2] / ".auth" / "cbs_state.json"
AUTH.parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=False,
        args=["--disable-popup-blocking"],
    )
    context = browser.new_context()
    page = context.new_page()

    page.goto(LEAGUE_URL, wait_until="domcontentloaded")

    print("Log in to CBS Sports in the browser.")
    input("After the league page loads, press Enter here...")

    context.storage_state(path=str(AUTH))
    browser.close()

print(f"Authentication state saved to: {AUTH.resolve()}")