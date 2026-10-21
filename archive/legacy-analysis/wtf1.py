from urllib.parse import urlsplit, parse_qs

captured_token = None


def capture_token(request):
    global captured_token

    parsed = urlsplit(request.url)

    if parsed.path == "/api/league/feed":
        token = parse_qs(parsed.query).get("access_token")
        if token:
            captured_token = token[0]
            print("[TOKEN] Captured securely")

    page.on("request", capture_token)

    page.wait_for_timeout(5000)

    if not captured_token:
        print("[TEST] Token was not captured")
    else:
        result = page.evaluate(
            """async ({token}) => {
                const params = new URLSearchParams({
                    version: "3.0",
                    response_format: "json",
                    access_token: token
                });

                const response = await fetch(
                    `/api/league/teams?${params.toString()}`,
                    { credentials: "include" }
                );

                const text = await response.text();

                return {
                    status: response.status,
                    contentType: response.headers.get("content-type"),
                    body: text
                };
            }""",
            {"token": captured_token},
        )

        print("[TEAMS TEST] Status:", result["status"])
        print("[TEAMS TEST] Type:", result["contentType"])

        try:
            teams_data = json.loads(result["body"])
            Path("discovery_output/teams_test.json").write_text(
                json.dumps(teams_data, indent=2),
                encoding="utf-8",
            )
            print("[SAVED] discovery_output/teams_test.json")
        except json.JSONDecodeError:
            Path("discovery_output/teams_test.html").write_text(
                result["body"],
                encoding="utf-8",
            )
            print("[NOT JSON] Saved response as teams_test.html")