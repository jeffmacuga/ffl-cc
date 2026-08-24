from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    context = p.chromium.launch_persistent_context(
        user_data_dir=r"C:\Users\User\AppData\Local\Microsoft\Edge\User Data",
        channel="msedge",
        headless=False
    )

    page = context.new_page()

    page.goto("https://kjfha.football.cbssports.com/")

    print(page.url)
    print(page.title())

    input("Press Enter...")
    context.close()