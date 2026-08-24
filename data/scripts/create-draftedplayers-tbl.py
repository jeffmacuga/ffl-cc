import sqlite3

DB_FILE = "./fantasy.db"

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS drafted_players (
    draft_id TEXT,
    round_num INTEGER,
    pick_num INTEGER,
    team_name TEXT,
    player_name TEXT,
    position TEXT,
    PRIMARY KEY (draft_id, round_num, pick_num)
)
""")

conn.commit()
conn.close()

print("drafted_players table created successfully")