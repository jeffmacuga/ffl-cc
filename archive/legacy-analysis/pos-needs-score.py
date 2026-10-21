import sqlite3
import pandas as pd

TARGETS = {
    "QB": 1,
    "RB": 4,
    "WR": 4,
    "TE": 1
}

conn = sqlite3.connect("fantasy.db")

roster = pd.read_sql("""
SELECT position,
       COUNT(*) AS count
FROM my_roster
GROUP BY position
""", conn)

counts = {
    row["position"]: row["count"]
    for _, row in roster.iterrows()
}

print("\nPosition Needs\n")

for pos, target in TARGETS.items():

    current = counts.get(pos, 0)

    need = target - current

    if need > 0:
        print(
            f"{pos}: HIGH NEED ({need} remaining)"
        )
    else:
        print(
            f"{pos}: FILLED"
        )

conn.close()