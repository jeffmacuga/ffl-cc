import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent / "fantasy.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


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