import pandas as pd
import sqlite3

df = pd.read_csv("imports/mock_draft.csv")

conn = sqlite3.connect("fantasy.db")

df.to_sql(
    "drafted_players",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print(f"Loaded {len(df)} draft picks")