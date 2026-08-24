import sqlite3
import pandas as pd

conn = sqlite3.connect("fantasy.db")

df = pd.read_sql("""
SELECT position,
       COUNT(*) AS count
FROM my_roster
GROUP BY position
""", conn)

print(df)

conn.close()