import streamlit as st
from config import LEAGUES, set_streamlit_config
from pages.lineup_preview import show_lineup_preview
from pages.standings import show_standings
from pages.rosters import show_team_rosters
from pages.matchups import show_matchups
from services.database import initialize_database


def get_selected_league():
    selected_name = st.session_state.get("selected_league_name", LEAGUES[0]["name"])
    selected_league = next(
        (league for league in LEAGUES if league["name"] == selected_name),
        LEAGUES[0],
    )
    return selected_league, selected_league["name"]


def render_standings():
    selected_league, selected_league_name = get_selected_league()
    show_standings(selected_league, selected_league_name)


def render_team_rosters():
    selected_league, selected_league_name = get_selected_league()
    show_team_rosters(selected_league, selected_league_name)


def render_lineup_preview():
    selected_league, selected_league_name = get_selected_league()
    show_lineup_preview(selected_league, selected_league_name)


def render_matchups():
    selected_league, selected_league_name = get_selected_league()
    show_matchups(selected_league, selected_league_name)


initialize_database()
set_streamlit_config()

page = st.navigation(
    {
        "League": [
            st.Page(render_standings, title="Standings", default=True),
            st.Page(render_matchups, title="Weekly Matchups"),
            st.Page(render_team_rosters, title="Team Rosters"),
        ],
        "Tools": [
            st.Page(render_lineup_preview, title="Lineup Preview"),
        ],
    },
    position="top",
)

_, league_selector = st.columns([5, 2])
with league_selector:
    st.selectbox(
        "League",
        options=[league["name"] for league in LEAGUES],
        key="selected_league_name",
        label_visibility="collapsed",
        help="Choose which fantasy league to view.",
    )

page.run()