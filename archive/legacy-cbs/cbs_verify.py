from cbs_normalize import normalize_cbs_rosters

with open("cbs_state.json", "r") as f:
    state = json.load(f)

for cookie in state["cookies"]:
    name = cookie["name"].lower()

    if any(x in name for x in [
        "auth",
        "login",
        "session",
        "token",
        "user",
        "identity"
    ]):
        print(cookie["name"], cookie["domain"])