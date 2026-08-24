from data.db import get_connection
import pandas as pd

def get_roster_requirements():

    query = """
    SELECT *
    FROM roster_requirements
    """

    with get_connection() as conn:
        return pd.read_sql_query(query, conn)