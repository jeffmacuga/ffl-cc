import sqlite3
import pandas as pd
from services.database import DB_FILE

def get_cbs_teams():
    conn = sqlite3.connect(DB_FILE)

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
    conn = sqlite3.connect(DB_FILE)

    df = pd.read_sql_query("""
        SELECT
            provider_player_id,
            player_name,
            position,
            eligible_positions,
            pro_team,
            bye_week,
            projected_points,
            average_points,
            ytd_points,
            roster_position,
            roster_status,
            updated_at
        FROM cbs_rosters
        WHERE provider_team_id = ?
    """, conn, params=(provider_team_id,))

    conn.close()

    return df