import sqlite3

conn = sqlite3.connect("fantasy.db")

conn.execute("""
DROP TABLE IF EXISTS my_roster
""")

conn.commit()
conn.close()

print("my_roster table deleted")
