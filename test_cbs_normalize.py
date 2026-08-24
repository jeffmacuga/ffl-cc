import json
from pathlib import Path

from cbs_normalize import normalize_cbs_rosters
from cbs_sqlite import import_cbs_rosters


DB_PATH = "C:\\Users\\User\\source\\ffl-mgr\\fantasy.db"

data = json.loads(
    Path("discovery_output/rosters_test.json")
    .read_text(encoding="utf-8")
)

teams, players = normalize_cbs_rosters(data)

import_cbs_rosters(
    db_path=DB_PATH,
    teams=teams,
    players=players,
)

print(f"Imported {len(teams)} team(s)")
print(f"Imported {len(players)} player(s)")