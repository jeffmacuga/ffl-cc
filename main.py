import streamlit as st
from config import LEAGUES, set_streamlit_config
from pages.lineup_preview import show_lineup_preview
from pages.standings import show_standings
from pages.rosters import show_team_rosters
from pages.matchups import show_matchups
from pages.trade_analyzer import show_trade_analyzer
from services.database import initialize_database
from services.access_control import (
    get_authenticated_league_names,
    require_site_access,
)


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


def render_trade_analyzer():
    selected_league, _ = get_selected_league()
    show_trade_analyzer(selected_league)


set_streamlit_config()

authenticated_leagues = get_authenticated_league_names()
if authenticated_leagues is None:
    accessible_league_names = [league["name"] for league in LEAGUES]
else:
    accessible_league_names = [
        league["name"]
        for league in LEAGUES
        if league["name"] in authenticated_leagues
    ]

if len(accessible_league_names) > 1:
    if st.session_state.get("selected_league_name") not in accessible_league_names:
        st.session_state["selected_league_name"] = accessible_league_names[0]
    st.sidebar.selectbox(
        "League",
        options=accessible_league_names,
        key="selected_league_name",
        help="Choose which fantasy league to view.",
    )
elif len(accessible_league_names) == 1:
    st.session_state["selected_league_name"] = accessible_league_names[0]

if not require_site_access():
    st.stop()

initialize_database()

page = st.navigation(
    {
        "League": [
            st.Page(render_standings, title="Standings", default=True),
            st.Page(render_matchups, title="Weekly Matchups"),
            st.Page(render_team_rosters, title="Team Rosters"),
        ],
        "Tools": [
            st.Page(render_lineup_preview, title="Lineup Preview"),
            st.Page(render_trade_analyzer, title="Trade Analyzer"),
        ],
    },
    position="sidebar",
)

page.run()
