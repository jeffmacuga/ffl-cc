import sqlite3
import pandas as pd

def get_cbs_teams():
    conn = sqlite3.connect("C:\\Users\\User\\source\\ffl-mgr\\fantasy.db")

    df = pd.read_sql_query("""
        SELECT
            provider_team_id,
            team_name,
            abbreviation,
            division
        FROM cbs_teams
        ORDER BY team_name
    """, conn)

    conn.close()
    return df

def get_cbs_roster(provider_team_id):
    conn = sqlite3.connect("C:\\Users\\User\\source\\ffl-mgr\\fantasy.db")

    df = pd.read_sql_query("""
        SELECT
            player_name,
            position
        FROM cbs_rosters
        WHERE provider_team_id = ?
    """, conn, params=(provider_team_id,))

    conn.close()

    return df