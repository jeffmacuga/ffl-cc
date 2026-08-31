import streamlit as st
from config import LEAGUES, set_streamlit_config
from pages.standings import show_standings
from pages.rosters import show_team_rosters
from services.database import initialize_database

initialize_database()
set_streamlit_config()

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Team Rosters", "Standings"])

league_names = [l["name"] for l in LEAGUES]
selected_league_name = st.sidebar.selectbox("Select League", league_names)
selected_league = next(l for l in LEAGUES if l["name"] == selected_league_name)

if page == "Standings":
    show_standings(selected_league, selected_league_name)
elif page == "Team Rosters":
    show_team_rosters(selected_league, selected_league_name)