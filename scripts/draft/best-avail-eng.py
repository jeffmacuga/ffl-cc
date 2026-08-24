def get_best_available(conn):

    query = """
    SELECT *
    FROM player_rankings
    WHERE player_id NOT IN (
        SELECT player_id
        FROM drafted_players
    )
    ORDER BY overall_rank ASC
    LIMIT 25
    """

    return pd.read_sql(query, conn)