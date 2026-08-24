import sqlite3

conn = sqlite3.connect("C:\\Users\\User\\source\\ffl-mgr\\fantasy.db")

cursor = conn.execute(
    "PRAGMA table_info(drafted_players)"
)

for row in cursor.fetchall():
    print(row)

conn.close()