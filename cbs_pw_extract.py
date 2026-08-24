import json
import requests

with open("cbs_state.json", "r") as f:
    state = json.load(f)

session = requests.Session()

for cookie in state["cookies"]:
    session.cookies.set(
        cookie["name"],
        cookie["value"],
        domain=cookie["domain"]
    )

r = session.get(
    "https://kjfha.football.cbssports.com/",
    allow_redirects=True
)

print(r.url)
print(r.status_code)

page.on(
    "response",
    lambda r: print(r.url)
)