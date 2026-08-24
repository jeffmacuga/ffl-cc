import sqlite3
import pandas as pd

conn = sqlite3.connect("fantasy.db")

df = pd.read_sql(
    "SELECT * FROM player_rankings",
    conn
)

print(df)