"""SQLite data-access helpers for CBS fantasy football in Streamlit."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


DEFAULT_DB_PATH = Path(
    os.getenv("FANTASY_DB_PATH", r"C:\Users\User\source\ffl-mgr\fantasy.db")
)


def _db_path(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Fantasy database not found: {path}")
    return path


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _decode_positions(value: Any) -> list[str]:
    """Convert stored JSON or delimited position text into a clean list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text:
        return []

    try:
        decoded = json.loads(text)
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
        if isinstance(decoded, dict):
            return [str(item).strip() for item in decoded.keys()]
        if isinstance(decoded, str):
            text = decoded
    except json.JSONDecodeError:
        pass

    separator = "," if "," in text else "/" if "/" in text else None
    if separator:
        return [item.strip() for item in text.split(separator) if item.strip()]
    return [text]


@st.cache_data(show_spinner=False)
def get_cbs_teams(db_path: str | Path | None = None) -> pd.DataFrame:
    """Return every CBS team for the Streamlit team selector."""
    query = """
        SELECT
            provider_team_id,
            team_name,
            abbreviation,
            division,
            logo_url,
            updated_at
        FROM cbs_teams
        ORDER BY team_name COLLATE NOCASE
    """
    with _connect(db_path) as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data(show_spinner=False)
def get_cbs_roster(
    provider_team_id: str,
    db_path: str | Path | None = None,
) -> pd.DataFrame:
    """Return one CBS roster selected by provider_team_id."""
    if not provider_team_id:
        return pd.DataFrame()

    query = """
        SELECT
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
            ytd_points,
            updated_at
        FROM cbs_rosters
        WHERE provider_team_id = ?
        ORDER BY
            CASE roster_position
                WHEN 'QB' THEN 1
                WHEN 'RB' THEN 2
                WHEN 'WR' THEN 3
                WHEN 'TE' THEN 4
                WHEN 'FLEX' THEN 5
                WHEN 'K' THEN 6
                WHEN 'DST' THEN 7
                WHEN 'DEF' THEN 7
                WHEN 'BN' THEN 8
                WHEN 'BENCH' THEN 8
                WHEN 'IR' THEN 9
                ELSE 10
            END,
            player_name COLLATE NOCASE
    """
    with _connect(db_path) as conn:
        roster = pd.read_sql_query(query, conn, params=(str(provider_team_id),))

    if not roster.empty:
        roster["eligible_positions_list"] = roster["eligible_positions"].apply(
            _decode_positions
        )
    return roster


@st.cache_data(show_spinner=False)
def get_cbs_team_summary(db_path: str | Path | None = None) -> pd.DataFrame:
    """Return each CBS team and its imported player count."""
    query = """
        SELECT
            t.provider_team_id,
            t.team_name,
            t.abbreviation,
            t.division,
            COUNT(r.provider_player_id) AS player_count,
            MAX(r.updated_at) AS roster_updated_at
        FROM cbs_teams AS t
        LEFT JOIN cbs_rosters AS r
            ON r.provider_team_id = t.provider_team_id
        GROUP BY
            t.provider_team_id,
            t.team_name,
            t.abbreviation,
            t.division
        ORDER BY t.team_name COLLATE NOCASE
    """
    with _connect(db_path) as conn:
        return pd.read_sql_query(query, conn)


def clear_cbs_cache() -> None:
    """Clear cached CBS queries after an import or database update."""
    get_cbs_teams.clear()
    get_cbs_roster.clear()
    get_cbs_team_summary.clear()


def render_cbs_team_selector(
    label: str = "CBS team",
    db_path: str | Path | None = None,
    key: str = "cbs_team_selector",
) -> tuple[str | None, pd.DataFrame]:
    """Render a team selector and return (team_id, selected roster)."""
    teams = get_cbs_teams(db_path)
    if teams.empty:
        st.warning("No CBS teams are currently available in the database.")
        return None, pd.DataFrame()

    team_ids = teams["provider_team_id"].astype(str).tolist()
    labels = dict(
        zip(teams["provider_team_id"].astype(str), teams["team_name"])
    )

    selected_team_id = st.selectbox(
        label,
        options=team_ids,
        format_func=lambda team_id: labels.get(team_id, team_id),
        key=key,
    )
    return selected_team_id, get_cbs_roster(selected_team_id, db_path)
