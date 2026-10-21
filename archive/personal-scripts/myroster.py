import sqlite3

conn = sqlite3.connect("fantasy.db")

conn.execute("""
CREATE TABLE IF NOT EXISTS my_roster (
    draft_id TEXT,
    round_num INTEGER,
    pick_num INTEGER,
    player_name TEXT,
    position TEXT,
    PRIMARY KEY (draft_id, player_name)
)
""")

conn.commit()
conn.close()

print("my_roster table created")
