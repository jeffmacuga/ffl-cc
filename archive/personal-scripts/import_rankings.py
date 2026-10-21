import sqlite3
import pandas as pd

CSV_FILE = "imports/player_rankings.csv"
DB_FILE = "fantasy.db"

df = pd.read_csv(CSV_FILE)

conn = sqlite3.connect(DB_FILE)

# Clear old rankings
conn.execute("DELETE FROM player_rankings")

# Import new rankings
df.to_sql(
    "player_rankings",
    conn,
    if_exists="append",
    index=False
)

conn.commit()
conn.close()

print(f"Imported {len(df)} players")