from data.db import get_connection
import pandas as pd


def get_available_players():

    query = """
    SELECT
        pr.player_name,
        pr.position,
        pr.ranking,
        pr.adp,
        pr.projected_points,
        pr.tier
    FROM player_rankings pr
    LEFT JOIN drafted_players dp
        ON pr.player_name = dp.player_name
    WHERE dp.player_name IS NULL
    ORDER BY pr.ranking
    """

    with get_connection() as conn:
        return pd.read_sql_query(query, conn)