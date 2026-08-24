from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=False)

    context = browser.new_context(
        storage_state="cbs_state.json"
    )

    page = context.new_page()

    page.goto(
        "https://kjfha.football.cbssports.com/",
        wait_until="networkidle"
    )

    print("URL:", page.url)
    print("Title:", page.title())

    print("MBFFL" in page.content())

    input("Press Enter...")