from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    context = browser.new_context()
    page = context.new_page()

    page.goto(
        "https://www.cbssports.com/login"
    )

    input("Log in manually, then press ENTER...")

    context.storage_state(path="cbs_state.json")