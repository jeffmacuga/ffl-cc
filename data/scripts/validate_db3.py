import pandas as pd
import sqlite3

conn = sqlite3.connect("C:\\Users\\User\\source\\ffl-mgr\\fantasy.db")

cursor = conn.cursor()

cursor.execute("""
DELETE FROM drafted_players
WHERE player_name = 'TEST_PLAYER';
""")

cursor.execute("""
DELETE FROM my_roster
WHERE player_name = 'TEST_PLAYER';
""")

conn.close()