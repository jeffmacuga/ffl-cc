# data/repositories/draft_repo.py

import pandas as pd
from data.db import get_connection


def get_draft_history(limit=25):

    query = f"""
    SELECT
        draft_id,
        player_name,
        position,
        drafted_at
    FROM drafted_players
    ORDER BY draft_id DESC
    LIMIT {limit}
    """

    with get_connection() as conn:
        return pd.read_sql_query(query, conn)