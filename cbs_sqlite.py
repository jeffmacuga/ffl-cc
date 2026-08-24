import sqlite3


def create_cbs_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cbs_teams (
            provider_team_id TEXT PRIMARY KEY,
            team_name TEXT NOT NULL,
            abbreviation TEXT,
            division TEXT,
            logo_url TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cbs_rosters (
            provider_team_id TEXT NOT NULL,
            provider_player_id TEXT NOT NULL,
            player_name TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            position TEXT,
            eligible_positions TEXT,
            pro_team TEXT,
            roster_position TEXT,
            roster_status TEXT,
            bye_week INTEGER,
            keeper INTEGER NOT NULL DEFAULT 0,
            projected_points REAL,
            average_points REAL,
            ytd_points REAL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (
                provider_team_id,
                provider_player_id
            ),

            FOREIGN KEY (provider_team_id)
                REFERENCES cbs_teams(provider_team_id)
                ON DELETE CASCADE
        );
    """)


def upsert_team(conn, team):
    conn.execute(
        """
        INSERT INTO cbs_teams (
            provider_team_id,
            team_name,
            abbreviation,
            division,
            logo_url
        )
        VALUES (?, ?, ?, ?, ?)

        ON CONFLICT(provider_team_id)
        DO UPDATE SET
            team_name = excluded.team_name,
            abbreviation = excluded.abbreviation,
            division = excluded.division,
            logo_url = excluded.logo_url,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            team["provider_team_id"],
            team["team_name"],
            team.get("abbreviation"),
            team.get("division"),
            team.get("logo_url"),
        ),
    )


def upsert_player(conn, player):
    conn.execute(
        """
        INSERT INTO cbs_rosters (
            provider_team_id,
            provider_player_id,
            player_name,
            first_name,
            last_name,
            position,
            eligible_positions,
            pro_team,
            roster_position,
            roster_status,
            bye_week,
            keeper,
            projected_points,
            average_points,
            ytd_points
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(
            provider_team_id,
            provider_player_id
        )
        DO UPDATE SET
            player_name = excluded.player_name,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            position = excluded.position,
            eligible_positions = excluded.eligible_positions,
            pro_team = excluded.pro_team,
            roster_position = excluded.roster_position,
            roster_status = excluded.roster_status,
            bye_week = excluded.bye_week,
            keeper = excluded.keeper,
            projected_points = excluded.projected_points,
            average_points = excluded.average_points,
            ytd_points = excluded.ytd_points,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            player["provider_team_id"],
            player["provider_player_id"],
            player["player_name"],
            player.get("first_name"),
            player.get("last_name"),
            player.get("position"),
            player.get("eligible_positions"),
            player.get("pro_team"),
            player.get("roster_position"),
            player.get("roster_status"),
            player.get("bye_week"),
            int(player.get("keeper", False)),
            player.get("projected_points"),
            player.get("average_points"),
            player.get("ytd_points"),
        ),
    )


def import_cbs_rosters(db_path, teams, players):
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        create_cbs_tables(conn)

        for team in teams:
            upsert_team(conn, team)

        for player in players:
            upsert_player(conn, player)

        # The context manager commits automatically.