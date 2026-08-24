import sqlite3

DB_PATH = r"C:\Users\User\source\ffl-mgr\fantasy.db"

with sqlite3.connect(DB_PATH) as conn:
    team_count = conn.execute(
        "SELECT COUNT(*) FROM cbs_teams"
    ).fetchone()[0]

    print(f"Teams imported: {team_count}")

    rows = conn.execute("""
        SELECT
            t.provider_team_id,
            t.team_name,
            COUNT(r.provider_player_id) AS player_count
        FROM cbs_teams AS t
        LEFT JOIN cbs_rosters AS r
            ON r.provider_team_id = t.provider_team_id
        GROUP BY
            t.provider_team_id,
            t.team_name
        ORDER BY t.team_name
    """).fetchall()

    for team_id, team_name, player_count in rows:
        print(f"{team_id}: {team_name} — {player_count} players")