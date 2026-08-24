import sqlite3

DB_PATH = "C:\\Users\\User\\source\\ffl-mgr\\fantasy.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS roster_requirements (
    position TEXT PRIMARY KEY,
    required_count INTEGER NOT NULL
)
""")

# Clear existing data
cursor.execute("DELETE FROM roster_requirements")

# Insert requirements
requirements = [
    ("QB", 1),
    ("RB", 2),
    ("WR", 2),
    ("TE", 1),
    ("FLEX", 1),
    ("BENCH", 6)
]

cursor.executemany("""
INSERT INTO roster_requirements (
    position,
    required_count
)
VALUES (?, ?)
""", requirements)

conn.commit()

print("✅ roster_requirements populated")

rows = cursor.execute(
    "SELECT * FROM roster_requirements"
).fetchall()

for row in rows:
    print(row)

conn.close()