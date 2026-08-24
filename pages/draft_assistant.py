import streamlit as st

from services.recommendation_service import (
    get_recommendations,
    filter_by_position
)

from services.draft_service import draft_player
from data.repositories.roster_repo import get_my_roster

from data.repositories.draft_repo import (
    get_draft_history
)

st.set_page_config(
    page_title="Draft Assistant",
    layout="wide"
)

st.title("🏈 Fantasy Football Command Center")

# ------------------------------------------------
# Refresh
# ------------------------------------------------

if st.button("🔄 Refresh Recommendations"):
    st.cache_data.clear()

# ------------------------------------------------
# Load Data
# ------------------------------------------------

data = get_recommendations()

recommendations = data["recommendations"]
roster_needs = data["roster_needs"]
available_players = data["available_players"]

# ------------------------------------------------
# Summary Metrics
# ------------------------------------------------

m1, m2, m3 = st.columns(3)

m1.metric(
    "Available Players",
    len(available_players)
)

m2.metric(
    "Recommendations",
    len(recommendations)
)

m3.metric(
    "Roster Needs",
    sum(roster_needs.values())
)

# ------------------------------------------------
# Position Filter
# ------------------------------------------------

position_filter = st.selectbox(
    "Position Filter",
    ["ALL", "QB", "RB", "WR", "TE"]
)

recommendations = filter_by_position(
    recommendations,
    position_filter
)

available_players = filter_by_position(
    available_players,
    position_filter
)

# ------------------------------------------------
# Dashboard Layout
# ------------------------------------------------

col1, col2, col3, col4 = st.columns([1, 1, 2, 1])

# =================================================
# NEEDS PANEL
# =================================================

with col1:

    st.subheader("📋 Roster Needs")

    for pos, value in roster_needs.items():

        st.metric(
            label=pos,
            value=value
        )

# =================================================
# MY ROSTER
# =================================================

with col2:

    st.subheader("🏈 My Roster")

    my_roster = get_my_roster()

    if my_roster.empty:

        st.info("No players drafted yet")

    else:

        for _, player in my_roster.iterrows():

            st.markdown(
                f"""
                **{player['player_name']}**

                {player['position']}
                """
            )

# =================================================
# RECOMMENDATIONS
# =================================================

with col3:

    st.subheader("🏆 Top Recommendations")

    top25 = recommendations.head(25)

    for _, player in top25.iterrows():

        c1, c2, c3 = st.columns([5, 1, 1])

        with c1:

            st.markdown(
                f"""
                **{player['player_name']}**

                {player['position']} |
                Score: **{player['score']}**

                _{player['reason']}_
                """
            )

        with c2:

            if st.button(
                "✅ My Pick",
                key=f"mine_{player['player_name']}"
            ):

                draft_player(
                    player_name=player["player_name"],
                    position=player["position"],
                    my_pick=True
                )

                st.rerun()

        with c3:

            if st.button(
                "❌ Taken",
                key=f"taken_{player['player_name']}"
            ):

                draft_player(
                    player_name=player["player_name"],
                    position=player["position"],
                    my_pick=False
                )

                st.rerun()

        st.divider()

# =================================================
# BEST AVAILABLE
# =================================================

with col4:

    st.subheader("⭐ Best Available")

    top_available = available_players.head(15)

    for _, player in top_available.iterrows():

        st.markdown(
            f"""
            **{player['player_name']}**

            {player['position']}
            Rank: {player['ranking']}
            """
        )