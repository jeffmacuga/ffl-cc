from playwright.sync_api import sync_playwright
import json

def handle_response(response):
    if "kjfha.football.cbssports.com" in response.url:
        print(response.url)

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="msedge",
        headless=False
    )

    context = browser.new_context(
        storage_state="cbs_state.json"
    )

    page = context.new_page()

    page.on("response", handle_response)

    page.goto(
        "https://kjfha.football.cbssports.com/",
        wait_until="domcontentloaded",
        timeout=60000
    )

    input("Navigate around league, then press Enter...")
