import sqlite3

conn = sqlite3.connect("C:\\Users\\User\\source\\ffl-mgr\\fantasy.db")

cursor = conn.cursor()

# Correct SQL to get all table names in SQLite
cursor.execute("""
SELECT * FROM sqlite_master WHERE type='table';
""")

tables = cursor.fetchall()

print("Tables:")
for table in tables:
    print(table[0])

conn.close()
