from playwright.sync_api import sync_playwright

def handle_request(request):
    if request.method == "POST":
        print("\nURL:", request.url)

        try:
            print(request.post_data)
        except Exception:
            pass



with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="msedge",
        headless=False
    )

    context = browser.new_context(
        storage_state="cbs_state.json"
    )

    page = context.new_page()

    page.on("request", handle_request)

    page.goto(
        "https://kjfha.football.cbssports.com/"
    )

    input("Navigate around and press Enter...")