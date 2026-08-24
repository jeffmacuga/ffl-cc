with open("cbs_source.html", "r", encoding="utf-8") as f:
    html = f.read()

for team in [
    "Big Ern",
    "3MTA3",
    "Kalifornication"
]:
    print(team, team in html)