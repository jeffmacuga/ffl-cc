import streamlit as st
import pandas as pd
from cbs_get_league import get_cbs_teams, get_cbs_roster
from pages.standings import load_espn_league
from services.database import format_last_data_sync

# Position maps for each platform
ESPN_POSITION_MAP = {
    "QB": ["QB"],
    "RB": ["RB"],
    "WR": ["WR"],
    "TE": ["TE"],
    "K": ["K"],
    "DL": ["DE", "DT", "DL"],
    "LB": ["LB"],
    "DB": ["S", "CB", "DB"],
    "FLEX": ["RB", "WR", "TE"]
}

CBS_POSITION_MAP = {
    "QB": ["QB"],
    "RB": ["RB"],
    "WR": ["WR"],
    "TE": ["TE"],
    "K": ["K"],
    "DST": ["DST", "D/ST", "DEF"],
    "SFLEX": ["QB", "RB", "WR", "TE"]
}


def reorder_roster_df(roster_df, platform):
    if platform == "ESPN":
        DISPLAY_ORDER = [
            "QB",
            "RB",
            "WR",
            "TE",
            "RB/WR/TE",
            "K",
            "DL",
            "LB",
            "DB"
        ]
    elif platform == "CBS":
        DISPLAY_ORDER = [
            "QB",
            "RB",
            "WR",
            "TE",
            "SUPERFLEX",
            "K",
            "DST"
        ]
    else:
        return roster_df

    if "Position" in roster_df.columns:
        mask = roster_df["Position"].isin(DISPLAY_ORDER)
        roster_df = roster_df[mask]
        roster_df["Position"] = pd.Categorical(roster_df["Position"], DISPLAY_ORDER)
        roster_df = roster_df.sort_values("Position")
    return roster_df


def build_espn_roster_df(roster):
    rows = []
    for player in roster:
        rows.append({
            "Player": player.name,
            "Position": player.position,
            "NFL Team": player.proTeam,
            "Roster Slot": player.lineupSlot,
            "Injury Status": player.injuryStatus or (
                "Injured" if player.injured else "Healthy"
            ),
            "Acquisition": player.acquisitionType,
            "Season Points": player.total_points,
            "Season Avg. Points": player.avg_points,
            "Projected Season Points": player.projected_total_points,
            "Projected Avg. Points": player.projected_avg_points
        })
    return pd.DataFrame(rows)


def show_team_rosters(selected_league, selected_league_name):
    st.header("Team Rosters")
    if selected_league["platform"] == "ESPN":
        league = load_espn_league(selected_league)
        st.caption(format_last_data_sync("ESPN", selected_league_name))
        espn_rows = []
        for team in league.teams:
            espn_rows.append({
                "platform": "ESPN",
                "provider_team_id": str(team.team_id),
                "team_name": team.team_name
            })
        teams_df = pd.DataFrame(espn_rows)
    elif selected_league["platform"] == "CBS":
        st.caption(format_last_data_sync("CBS", selected_league_name))
        cbs_df = get_cbs_teams()
        cbs_df["platform"] = "CBS"
        teams_df = cbs_df.rename(columns={"team_name": "team_name", "team_id": "provider_team_id"})
    else:
        st.info("Team rosters not available for this league yet.")
        return

    teams_df["label"] = teams_df["team_name"]
    selected_label = st.selectbox("Choose Team", teams_df["label"])
    selected_team = teams_df[teams_df["label"] == selected_label].iloc[0]

    if selected_league["platform"] == "ESPN":
        team_obj = next(
            (t for t in league.teams if str(t.team_id) == str(selected_team["provider_team_id"])),
            None
        )
        if team_obj is None:
            st.error("ESPN team not found.")
            return
        roster_df = build_espn_roster_df(team_obj.roster)
        roster_df = reorder_roster_df(roster_df, "ESPN")
        st.dataframe(roster_df, width="stretch")
    elif selected_league["platform"] == "CBS":
        roster_df = get_cbs_roster(selected_team["provider_team_id"])
        roster_df.rename(columns={"player_name": "Player", "position": "Position"}, inplace=True)
        roster_df = reorder_roster_df(roster_df, "CBS")
        st.dataframe(roster_df, width="stretch")
