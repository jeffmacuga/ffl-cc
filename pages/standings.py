# pages/standings.py

import streamlit as st
import pandas as pd
import sqlite3
from espn_api.football import League
from services.database import DB_FILE, save_league_snapshot, save_rosters


def get_cbs_standings():
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query(
            "SELECT team_name AS 'Team', wins AS 'Wins', losses AS 'Losses', ties AS 'Ties', points_for AS 'Points For' FROM cbs_standings",
            conn
        )
    return df


def get_cbs_team_options():
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT team_id, team_name FROM cbs_standings ORDER BY team_name"
        ).fetchall()
    return [(str(team_id), str(team_name)) for team_id, team_name in rows]


def load_espn_league(selected_league):
    league = League(
        league_id=selected_league["league_id"],
        year=selected_league["year"],
        swid=selected_league["swid"],
        espn_s2=selected_league["espn_s2"]
    )
    save_league_snapshot(league)
    save_rosters(league)
    return league

def show_standings(selected_league, selected_league_name):
    st.header("Standings")
    if selected_league["platform"] == "ESPN":
        league = load_espn_league(selected_league)
        teams = league.teams
        rows = [
            {
                "Team": team.team_name,
                "Wins": team.wins,
                "Losses": team.losses,
                "Points For": round(team.points_for, 2)
            }
            for team in teams
        ]
        df = pd.DataFrame(rows)
        df = df.sort_values(["Wins", "Points For"], ascending=False)
        st.dataframe(df, use_container_width=True)
    elif selected_league["platform"] == "CBS":
        cbs_df = get_cbs_standings()
        if not cbs_df.empty:
            cbs_df = cbs_df.sort_values(["Wins", "Points For"], ascending=False)
            st.dataframe(cbs_df, use_container_width=True)
        else:
            st.info("No CBS standings data available.")
