from data.db import get_connection
import pandas as pd


def get_my_roster():

    query = """
    SELECT *
    FROM my_roster
    """

    with get_connection() as conn:
        return pd.read_sql_query(query, conn)