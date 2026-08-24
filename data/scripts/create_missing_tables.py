# create_missing_tables.py

import sqlite3

DB_PATH = "C:\\Users\\User\\source\\ffl-mgr\\fantasy.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# --------------------------------------------------
# Teams
# --------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    team_name TEXT,
    owner_name TEXT
)
""")

# --------------------------------------------------
# Rosters
# --------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS rosters (
    roster_id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER,
    player_name TEXT,
    position TEXT,
    nfl_team TEXT,
    FOREIGN KEY(team_id) REFERENCES teams(team_id)
)
""")

# --------------------------------------------------
# Player Rankings
# --------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS player_rankings (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    position TEXT NOT NULL,
    nfl_team TEXT,
    rank INTEGER,
    projected_points REAL,
    tier INTEGER,
    bye_week INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# --------------------------------------------------
# Drafted Players
# --------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS drafted_players (
    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    position TEXT,
    drafted_by_team_id INTEGER,
    pick_number INTEGER,
    round_number INTEGER,
    drafted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# --------------------------------------------------
# My Roster
# --------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS my_roster (
    roster_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    position TEXT NOT NULL,
    nfl_team TEXT,
    rank INTEGER,
    projected_points REAL
)
""")

conn.commit()

# --------------------------------------------------
# Verify
# --------------------------------------------------

tables = cursor.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
ORDER BY name
""").fetchall()

print("\nTables in database:")
for table in tables:
    print(f" - {table[0]}")

conn.close()

print("\n✅ Missing tables created successfully.")