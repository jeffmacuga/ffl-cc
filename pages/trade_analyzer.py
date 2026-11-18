import math

import pandas as pd
import streamlit as st
from espn_api.football.constant import POSITION_MAP

from optimizer import normalize_position
from pages.standings import load_espn_league
from cbs_get_league import get_cbs_roster, get_cbs_teams
from services.database import format_last_data_sync
from services.trade_analysis import analyze_trade


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _espn_roster_frame(team):
    rows = []
    for player in team.roster:
        projection = _number(
            getattr(player, "projected_avg_points", None)
        )
        if projection is None:
            projection = _number(
                getattr(player, "avg_points", None)
            )
        if projection is not None and projection <= 0:
            projection = None
        rows.append({
            "player_id": str(player.playerId),
            "player_name": player.name,
            "position": normalize_position(player.position),
            "projected_points": projection,
            "injury_status": getattr(player, "injuryStatus", ""),
        })
    return pd.DataFrame(
        rows,
        columns=["player_id", "player_name", "position", "projected_points"],
    )


def _cbs_roster_frame(roster):
    return pd.DataFrame({
        "player_id": roster["provider_player_id"].astype(str),
        "player_name": roster["player_name"],
        "position": roster["position"].map(normalize_position),
        "projected_points": roster["projected_points"],
    })


def _espn_lineup_requirements(league):
    supported_positions = (
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "DST",
        "DL",
        "LB",
        "DB",
        "RB/WR/TE",
    )
    requirements = dict.fromkeys(supported_positions, 0)
    unsupported_positions = set()
    slot_counts = getattr(
        getattr(league, "settings", None),
        "position_slot_counts",
        {},
    )
    for slot, count in slot_counts.items():
        try:
            count = int(count)
        except (TypeError, ValueError):
            unsupported_positions.add(str(slot))
            continue
        if count <= 0:
            continue

        if isinstance(slot, int):
            position = POSITION_MAP.get(slot)
        elif str(slot).isdigit():
            position = POSITION_MAP.get(int(slot))
        else:
            position = str(slot)
        if not position:
            unsupported_positions.add(str(slot))
            continue
        position = str(position).strip().upper()
        if position in {"BE", "IR", "ER", "ROOKIE"}:
            continue
        if position in {"FLEX", "D/ST", "DEF"}:
            position = {"FLEX": "RB/WR/TE", "D/ST": "DST", "DEF": "DST"}[
                position
            ]
        position = normalize_position(position)
        if position in requirements:
            requirements[position] = requirements.get(position, 0) + int(count)
        else:
            unsupported_positions.add(str(slot))
    return requirements, sorted(unsupported_positions)


def _player_label(player_lookup, player_id):
    player = player_lookup[player_id]
    projection = _number(player["projected_points"])
    projection_label = (
        f"{projection:.1f} pts"
        if projection is not None
        else "projection unavailable"
    )
    return (
        f"{player['player_name']} ({player['position']}, "
        f"{projection_label})"
    )


def _show_side_summary(title, result, roster_requirements):
    st.subheader(title)
    sent, received, net = st.columns(3)
    sent.metric("Projected points sent", f"{result['sent_projection']:.1f}")
    received.metric(
        "Projected points received",
        f"{result['received_projection']:.1f}",
    )
    net.metric(
        "Net projected points",
        f"{result['net_projection']:+.1f}",
        help="Received projection minus sent projection.",
    )
    if result["missing_projections"]:
        st.caption(
            f"{result['missing_projections']} selected player projection(s) "
            "were unavailable and are excluded from the totals."
        )
    st.dataframe(
        result["position_impact"],
        width="stretch",
        hide_index=True,
    )
    if roster_requirements:
        st.caption(
            "Fixed starting-slot counts are shown for context. Flex, bench, "
            "and IR slots are excluded; roster counts include all players."
        )
    else:
        st.caption(
            "CBS lineup requirements are not stored locally, so roster fit "
            "is shown as the before/after position mix."
        )
    lineup_impact = result.get("lineup_impact")
    if lineup_impact:
        st.markdown("**Optimized starting lineup impact**")
        before, after, change = st.columns(3)
        before.metric(
            "Before",
            f"{lineup_impact['before_projection']:.1f} pts",
        )
        after.metric(
            "After",
            f"{lineup_impact['after_projection']:.1f} pts",
        )
        change.metric(
            "Change",
            f"{lineup_impact['change']:+.1f} pts",
            help=(
                "After-trade best projected starting lineup minus the "
                "current best projected starting lineup."
            ),
        )
        before_lineup, after_lineup = st.columns(2)
        with before_lineup:
            st.caption("Best lineup before")
            st.dataframe(
                lineup_impact["before_lineup"],
                width="stretch",
                hide_index=True,
            )
        with after_lineup:
            st.caption("Best lineup after")
            st.dataframe(
                lineup_impact["after_lineup"],
                width="stretch",
                hide_index=True,
            )


def show_trade_analyzer(selected_league):
    st.header("Trade Analyzer")
    st.caption(
        "Select one or more players from each team. This read-only tool "
        "compares available projections and the resulting position mix. "
        "ESPN uses projected average points (falling back to average points) "
        "and compares optimized starting lineups when the league format is "
        "supported."
    )

    roster_requirements = {}
    lineup_requirements = None
    unsupported_slots = []
    if selected_league["platform"] == "ESPN":
        league = load_espn_league(selected_league)
        teams = {
            str(team.team_id): team
            for team in league.teams
        }
        team_labels = {
            team_id: team.team_name
            for team_id, team in teams.items()
        }
        if len(teams) < 2:
            st.info("At least two ESPN teams are needed to analyze a trade.")
            return

        your_team_id = st.selectbox(
            "Your team",
            options=list(teams),
            format_func=team_labels.get,
            key=f"trade_your_team_{selected_league['name']}",
        )
        partner_ids = [team_id for team_id in teams if team_id != your_team_id]
        partner_team_id = st.selectbox(
            "Trade partner",
            options=partner_ids,
            format_func=team_labels.get,
            key=f"trade_partner_{selected_league['name']}_{your_team_id}",
        )
        your_roster = _espn_roster_frame(teams[your_team_id])
        partner_roster = _espn_roster_frame(teams[partner_team_id])
        lineup_requirements, unsupported_slots = _espn_lineup_requirements(
            league
        )
        roster_requirements = {
            position: count
            for position, count in lineup_requirements.items()
            if count > 0
        }
    elif selected_league["platform"] == "CBS":
        teams_df = get_cbs_teams()
        if teams_df.empty:
            st.info("No CBS teams were found.")
            return
        teams = {
            str(row["provider_team_id"]): row["team_name"]
            for _, row in teams_df.iterrows()
        }
        team_labels = teams
        if len(teams) < 2:
            st.info("At least two CBS teams are needed to analyze a trade.")
            return

        your_team_id = st.selectbox(
            "Your team",
            options=list(teams),
            format_func=team_labels.get,
            key=f"trade_your_team_{selected_league['name']}",
        )
        partner_ids = [team_id for team_id in teams if team_id != your_team_id]
        partner_team_id = st.selectbox(
            "Trade partner",
            options=partner_ids,
            format_func=team_labels.get,
            key=f"trade_partner_{selected_league['name']}_{your_team_id}",
        )
        your_roster = _cbs_roster_frame(get_cbs_roster(your_team_id))
        partner_roster = _cbs_roster_frame(get_cbs_roster(partner_team_id))
    else:
        st.info("Trade analysis is not available for this league platform.")
        return

    st.caption(format_last_data_sync(
        selected_league["platform"],
        selected_league["name"],
    ))

    if your_roster.empty or partner_roster.empty:
        st.info("Both teams need roster data before a trade can be analyzed.")
        return
    if unsupported_slots:
        st.info(
            "Optimized lineup impact is unavailable because this league has "
            "unsupported starter slot(s): "
            + ", ".join(unsupported_slots)
            + ". Projected trade totals and position counts are still shown."
        )
        lineup_requirements = None

    your_players = your_roster.set_index("player_id").to_dict("index")
    partner_players = partner_roster.set_index("player_id").to_dict("index")
    your_column, partner_column = st.columns(2)
    with your_column:
        your_selections = st.multiselect(
            f"Players you send ({team_labels[your_team_id]})",
            options=list(your_players),
            format_func=lambda player_id: _player_label(
                your_players,
                player_id,
            ),
            key=f"trade_your_players_{your_team_id}",
        )
    with partner_column:
        partner_selections = st.multiselect(
            f"Players you receive ({team_labels[partner_team_id]})",
            options=list(partner_players),
            format_func=lambda player_id: _player_label(
                partner_players,
                player_id,
            ),
            key=f"trade_partner_players_{partner_team_id}",
        )

    if not your_selections or not partner_selections:
        st.info("Choose at least one player on each side to compare the trade.")
        return

    result = analyze_trade(
        your_roster,
        partner_roster,
        your_selections,
        partner_selections,
        roster_requirements,
        lineup_requirements,
    )
    your_column, partner_column = st.columns(2)
    with your_column:
        _show_side_summary(
            f"{team_labels[your_team_id]} roster after trade",
            result["your_side"],
            roster_requirements,
        )
    with partner_column:
        _show_side_summary(
            f"{team_labels[partner_team_id]} roster after trade",
            result["partner_side"],
            roster_requirements,
        )
