import re

with open("page.html", encoding="utf-8") as f:
    html = f.read()

patterns = [
    r'league_id[^"]*',
    r'leagueId[^"]*',
    r'"league_id"\s*:\s*"?(\d+)',
    r'"leagueId"\s*:\s*"?(\d+)',
    r'league_id=(\d+)',
]

for pattern in patterns:
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f"\nFound for {pattern}:")
        print(matches[:20])