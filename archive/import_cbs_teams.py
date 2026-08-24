import re
import sqlite3

with open(
    "cbs_source.html",
    "r",
    encoding="utf-8"
) as f:
    html = f.read()

pattern = re.compile(
    r'"division"\s*:\s*"([^"]+)".*?'
    r'"name"\s*:\s*"([^"]+)".*?'
    r'"id"\s*:\s*"(\d+)"',
    re.DOTALL
)

matches = pattern.findall(html)

print(f"Found {len(matches)} teams")

conn = sqlite3.connect("fantasy.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS cbs_teams (
    team_id INTEGER,
    team_name TEXT,
    division TEXT
)
""")

cursor.execute("DELETE FROM cbs_teams")

for division, team_name, team_id in matches:

    print(team_id, team_name, division)

    cursor.execute("""
    INSERT INTO cbs_teams
    VALUES (?, ?, ?)
    """, (
        int(team_id),
        team_name,
        division
    ))

conn.commit()
conn.close()