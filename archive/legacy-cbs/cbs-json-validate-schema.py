import json
from pathlib import Path

data = json.loads(
    Path("discovery_output/rosters_test.json")
    .read_text(encoding="utf-8")
)

rosters = data["body"]["rosters"]
teams = rosters["teams"]

for team in teams:
    print("\nTEAM")
    print("ID:", team.get("id"))
    print("Name:", team.get("name"))
    print("Players:", len(team.get("players", [])))

    for index, player in enumerate(team.get("players", [])[:2]):
        print(f"\nPlayer {index + 1} keys:")
        print(list(player.keys()))

        for key, value in player.items():
            if isinstance(value, dict):
                print(f"  {key}: dict keys={list(value.keys())}")
            elif isinstance(value, list):
                print(f"  {key}: list length={len(value)}")
            else:
                print(f"  {key}: {type(value).__name__}")