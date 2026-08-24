import sqlite3

DB_FILE = "./fantasy.db"

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()


cursor.execute("""
CREATE TABLE draft_picks(
    league_id INTEGER,
    pick_number INTEGER,
    team_id INTEGER,
    player_id INTEGER,
    timestamp DATETIME
);
""")


conn.commit()
conn.close()

print("some other tables successfully")

