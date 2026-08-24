import sqlite3
import pandas as pd

conn = sqlite3.connect("../fantasy.db")

df = pd.read_sql_query(
    "SELECT * FROM player_rankings",
    conn
)

print(df)

conn.close()