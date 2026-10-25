import pandas as pd
import streamlit as st

from pages.standings import load_espn_league
from services.database import format_last_data_sync


def _team_name(team):
    return team.team_name if team is not None else "BYE"


def build_matchup_summary(box_scores):
    rows = []
    for box_score in box_scores:
        rows.append({
            "Away Team": _team_name(box_score.away_team),
            "Away Score": box_score.away_score,
            "Away Projected": box_score.away_projected,
            "Home Team": _team_name(box_score.home_team),
            "Home Score": box_score.home_score,
            "Home Projected": box_score.home_projected,
        })
    return pd.DataFrame(rows)


def build_matchup_player_rows(box_score, side):
    lineup = getattr(box_score, f"{side}_lineup")
    rows = []
    for player in lineup:
        if getattr(player, "on_bye_week", False):
            status = "Bye"
        elif not getattr(player, "game_date", None):
            status = "Unknown"
        elif player.game_played == 100:
            status = "Final"
        else:
            status = "Not final"
        rows.append({
            "Slot": player.slot_position,
            "Player": player.name,
            "NFL Team": player.proTeam,
            "Status": status,
            "Points": player.points,
            "Projected Points": player.projected_points,
        })
    return pd.DataFrame(rows)


def _format_matchup_label(box_score):
    return f"{_team_name(box_score.away_team)} at {_team_name(box_score.home_team)}"


def show_matchups(selected_league, selected_league_name):
    st.header("Weekly Matchups")
    if selected_league["platform"] != "ESPN":
        st.info(
            "Weekly matchup data is not available for this platform yet. "
            "The current CBS integration provides standings and rosters, "
            "but not matchup scores or projections."
        )
        return

    league = load_espn_league(selected_league)
    st.caption(format_last_data_sync("ESPN", selected_league_name))
    latest_week = max(1, int(league.current_week))
    week = st.selectbox(
        "Scoring week",
        options=list(range(1, latest_week + 1)),
        index=latest_week - 1,
        key=f"matchups_week_{selected_league_name}",
    )
    box_scores = league.box_scores(week=week)
    if not box_scores:
        st.info(f"No matchups are available for week {week}.")
        return

    st.subheader(f"All matchups — week {week}")
    st.dataframe(
        build_matchup_summary(box_scores),
        use_container_width=True,
        hide_index=True,
    )
    selected_matchup_index = st.selectbox(
        "Matchup",
        options=list(range(len(box_scores))),
        format_func=lambda index: _format_matchup_label(box_scores[index]),
        key=f"matchups_pairing_{selected_league_name}_{week}",
    )
    box_score = box_scores[selected_matchup_index]
    st.subheader(_format_matchup_label(box_score))

    away, home = st.columns(2)
    with away:
        st.metric(_team_name(box_score.away_team), f"{box_score.away_score:.2f}")
        st.caption(f"ESPN projected: {box_score.away_projected:.2f}")
    with home:
        st.metric(_team_name(box_score.home_team), f"{box_score.home_score:.2f}")
        st.caption(f"ESPN projected: {box_score.home_projected:.2f}")

    away_lineup, home_lineup = st.columns(2)
    with away_lineup:
        st.markdown(f"**{_team_name(box_score.away_team)} lineup**")
        st.dataframe(
            build_matchup_player_rows(box_score, "away"),
            use_container_width=True,
            hide_index=True,
        )
    with home_lineup:
        st.markdown(f"**{_team_name(box_score.home_team)} lineup**")
        st.dataframe(
            build_matchup_player_rows(box_score, "home"),
            use_container_width=True,
            hide_index=True,
        )
    st.caption(
        "Scores and player points are from ESPN. “Not final” means ESPN "
        "has not marked the player's NFL game complete; projected points "
        "are ESPN's matchup projections."
    )
