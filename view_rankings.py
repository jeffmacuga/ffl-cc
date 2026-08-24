import sqlite3
import pandas as pd

conn = sqlite3.connect("fantasy.db")

df = pd.read_sql("""
SELECT *
FROM player_rankings
ORDER BY ranking
LIMIT 25
""", conn)

print(df)

conn.close()