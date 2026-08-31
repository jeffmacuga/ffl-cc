# pages/standings.py

import streamlit as st
import pandas as pd
import sqlite3
from espn_api.football import League
from services.database import save_league_snapshot, save_rosters
from cbs_get_league import get_cbs_teams, get_cbs_roster  # Import CBS roster fetch
from optimizer import get_optimal_lineup, lineup_to_dataframe

CBS_DB_PATH = r"C:\Users\User\source\repos\ffl-cc\fantasy.db"


def get_cbs_standings():
    with sqlite3.connect(CBS_DB_PATH) as conn:
        df = pd.read_sql_query(
            "SELECT team_name AS 'Team', wins AS 'Wins', losses AS 'Losses', ties AS 'Ties', points_for AS 'Points For' FROM cbs_standings",
            conn
        )
    return df

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
    st.header(f"{selected_league_name} Standings")
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

        # --- Lineup Optimization Section ---
        st.subheader("Lineup Optimization")
        team_names = [team.team_name for team in teams]
        selected_team_name = st.selectbox("Select a team for optimization", team_names)
        selected_team = next((team for team in teams if team.team_name == selected_team_name), None)
        if selected_team:
            optimal_lineup = get_optimal_lineup(selected_team)
            if isinstance(optimal_lineup, tuple):
                optimal_lineup = optimal_lineup[0]
            lineup_df = lineup_to_dataframe(optimal_lineup)
            st.write(f"Optimal Lineup for {selected_team_name}:")
            st.dataframe(lineup_df, use_container_width=True)
        else:
            st.info("Select a team to view optimal lineup.")

    elif selected_league["platform"] == "CBS":
        cbs_df = get_cbs_standings()
        if not cbs_df.empty:
            cbs_df = cbs_df.sort_values(["Wins", "Points For"], ascending=False)
            st.dataframe(cbs_df, use_container_width=True)
        else:
            st.info("No CBS standings data available.")

          # --- CBS Lineup Optimization Section ---
        st.subheader("Lineup Optimization")
        # Use the original CBS teams DataFrame to get the team_id and team_name mapping
        original_cbs_df = get_cbs_teams()
        team_names = original_cbs_df["team_name"].tolist()
        selected_team_name = st.selectbox("Select a CBS team for optimization", team_names, key="cbs_opt")
        selected_team_row = original_cbs_df[original_cbs_df["team_name"] == selected_team_name]
        if not selected_team_row.empty and "team_id" in selected_team_row.columns:
            provider_team_id = selected_team_row.iloc[0]["team_id"]
            roster_df = get_cbs_roster(provider_team_id)
            if roster_df is not None and not roster_df.empty:
                st.write("Raw roster data:")
                st.dataframe(roster_df, use_container_width=True)
                try:
                    st.write(f"Roster columns: {list(roster_df.columns)}")
                    # Ensure projected_points is float and not all zeros or NaN
                    if "projected_points" in roster_df.columns:
                        roster_df["projected_points"] = pd.to_numeric(roster_df["projected_points"], errors="coerce")
                        if roster_df["projected_points"].isnull().all() or (roster_df["projected_points"] == 0).all():
                            st.warning("All projected points are missing or zero. Please check your data source.")
                    else:
                        st.error("Missing 'projected_points' column in roster data.")
                        return
                    # Check for required columns
                    required_cols = {"slot", "player", "projected_points"}
                    missing_cols = required_cols - set(roster_df.columns)
                    if missing_cols:
                        st.error(f"Missing columns in roster data: {missing_cols}")
                    else:
                        # Show the input to optimizer for debugging
                        st.write("Input to optimizer:")
                        st.dataframe(roster_df[["player", "slot", "projected_points"]], use_container_width=True)
                        optimal_lineup = get_optimal_lineup(roster_df)
                        if isinstance(optimal_lineup, tuple):
                            optimal_lineup = optimal_lineup[0]
                        lineup_df = lineup_to_dataframe(optimal_lineup)
                        if lineup_df is not None and not lineup_df.empty:
                            st.write(f"Optimal Lineup for {selected_team_name}:")
                            st.dataframe(lineup_df, use_container_width=True)
                            # Show difference between original and optimal
                            st.write("Lineup changes:")
                            merged = pd.merge(
                                roster_df[["player", "slot", "projected_points"]],
                                lineup_df[["player", "slot", "projected_points"]],
                                on="player",
                                how="outer",
                                suffixes=("_original", "_optimal")
                            )
                            merged["slot_changed"] = merged["slot_original"] != merged["slot_optimal"]
                            st.dataframe(merged, use_container_width=True)
                        else:
                            st.info("No optimal lineup data available for this team. Check optimizer output.")
                except Exception as e:
                    st.error(f"Error generating optimal lineup: {e}")
            else:
                st.info("No roster data available for this team.")
        else:
            st.info("Select a team to view optimal lineup or team_id not found.")
