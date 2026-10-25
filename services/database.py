import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent / "fantasy.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def record_data_sync(platform, league_name, synced_at=None):
    synced_at = synced_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(get_connection()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_syncs (
                platform TEXT NOT NULL,
                league_name TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (platform, league_name)
            )
        """)
        conn.execute("""
            INSERT INTO data_syncs (platform, league_name, synced_at)
            VALUES (?, ?, ?)
            ON CONFLICT(platform, league_name) DO UPDATE SET
                synced_at = excluded.synced_at
        """, (platform, league_name, synced_at))


def get_last_data_sync(platform, league_name=None):
    with closing(get_connection()) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "data_syncs" in tables:
            if league_name is None:
                row = conn.execute(
                    """
                    SELECT MAX(synced_at)
                    FROM data_syncs
                    WHERE platform = ?
                    """,
                    (platform,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT synced_at
                    FROM data_syncs
                    WHERE platform = ? AND league_name = ?
                    """,
                    (platform, league_name),
                ).fetchone()
            if row and row[0]:
                return row[0]

        if platform == "CBS" and "cbs_rosters" in tables:
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(cbs_rosters)")
            }
            if "updated_at" in columns:
                row = conn.execute(
                    "SELECT MAX(updated_at) FROM cbs_rosters"
                ).fetchone()
                return row[0] if row else None
        return None


def format_last_data_sync(platform, league_name=None):
    synced_at = get_last_data_sync(platform, league_name)
    return format_sync_timestamp(synced_at)


def format_sync_timestamp(synced_at):
    if not synced_at:
        return "Last data sync: not recorded"

    try:
        timestamp = datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
    except ValueError:
        return f"Last data sync: {synced_at} UTC"
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    return f"Last data sync: {timestamp:%b %d, %Y at %H:%M UTC}"


def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        team_id INTEGER,
        season INTEGER,
        team_name TEXT,
        wins INTEGER,
        losses INTEGER,
        points_for REAL,
        PRIMARY KEY(team_id, season)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rosters (
        season INTEGER,
        team_id INTEGER,
        player_name TEXT,
        position TEXT
    )
    """)

    conn.commit()
    conn.close()

def save_league_snapshot(league):

    conn = get_connection()
    cursor = conn.cursor()

    season = league.year

    print(f"Saving {len(league.teams)} teams")

    for team in league.teams:

        print(f"Saving {team.team_name}")

        cursor.execute("""
        INSERT OR REPLACE INTO teams (
            team_id,
            season,
            team_name,
            wins,
            losses,
            points_for
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            team.team_id,
            season,
            team.team_name,
            team.wins,
            team.losses,
            team.points_for
        ))

    conn.commit()

    print("Commit complete")

    conn.close()

def save_rosters(league):

    conn = get_connection()
    cursor = conn.cursor()

    season = league.year

    cursor.execute(
        "DELETE FROM rosters WHERE season=?",
        (season,)
    )

    for team in league.teams:

        for player in team.roster:

            cursor.execute("""
            INSERT INTO rosters (
                season,
                team_id,
                player_name,
                position
            )
            VALUES (?, ?, ?, ?)
            """, (
                season,
                team.team_id,
                player.name,
                player.position
            ))

    conn.commit()
    conn.close()

def create_rankings_table():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_rankings (
        player_name TEXT,
        position TEXT,
        ranking INTEGER,
        adp REAL,
        projected_points REAL,
        tier INTEGER
    )
    """)

    conn.commit()
    conn.close()