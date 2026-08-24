from data.db import get_connection


def draft_player(
    player_name,
    position,
    my_pick=False
):

    with get_connection() as conn:

        conn.execute(
            """
            INSERT INTO drafted_players
            (player_name, position)
            VALUES (?, ?)
            """,
            (player_name, position)
        )

        if my_pick:

            conn.execute(
                """
                INSERT INTO my_roster
                (player_name, position)
                VALUES (?, ?)
                """,
                (player_name, position)
            )

        conn.commit()