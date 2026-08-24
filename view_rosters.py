import sqlite3
import pandas as pd

conn = sqlite3.connect("fantasy.db")

df = pd.read_sql("""
SELECT *
FROM rosters
ORDER BY team_id, player_name
""", conn)

print(df.head(50))

conn.close()