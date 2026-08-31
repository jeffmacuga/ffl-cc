import sqlite3
import pandas as pd

conn = sqlite3.connect("C:\\Users\\User\\source\\repos\\ffl-cc\\fantasy.db")

cursor = conn.cursor()

team_id = "18"  # example

df = pd.read_sql_query("""
    SELECT *
    FROM cbs_standings
    """,
    conn,
    #params=(team_id,)
)

print(df)

#for row in cursor.fetchall():
 #   print(row)

conn.close()
