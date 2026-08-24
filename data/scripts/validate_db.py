import sqlite3

conn = sqlite3.connect("C:\\Users\\User\\source\\ffl-mgr\\fantasy.db")
cursor = conn.cursor()

tables = [
    "teams",
    "rosters",
    "player_rankings",
    "drafted_players",
    "my_roster",
    "leagues",
    "roster_requirements",
    "draft_picks"
]

print("\nTABLE COUNTS")
print("-" * 30)

for table in tables:
    count = cursor.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]

    print(f"{table:<20} {count}")

conn.close()
