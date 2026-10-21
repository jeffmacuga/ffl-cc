import sqlite3

MY_TEAM = "Rotten Johnnies"

conn = sqlite3.connect("fantasy.db")
cursor = conn.cursor()

# Check if required columns exist in drafted_players
cursor.execute("PRAGMA table_info(drafted_players)")
columns = {row[1] for row in cursor.fetchall()}

required_columns = {"round", "pick", "player", "position", "team"}
missing = required_columns - columns
if missing:
    raise Exception(f"Missing columns in drafted_players: {', '.join(missing)}")

# Clear my_roster table
cursor.execute("DELETE FROM my_roster")

# Insert updated roster
cursor.execute("""
INSERT INTO my_roster (
    round_num,
    pick_num,
    player_name,
    position
)
SELECT
    round,
    pick,
    player,
    position
FROM drafted_players
WHERE team = ?
""", (MY_TEAM,))

conn.commit()
conn.close()

print("Roster updated")
