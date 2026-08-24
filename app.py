import streamlit as st
import pandas as pd
import sqlite3

from espn_api.football import League

from optimizer import (
    get_optimal_lineup,
    get_current_lineup_score,
    calculate_player_score,
    lineup_to_dataframe
)

from services.database import (
    initialize_database,
    save_league_snapshot,
    save_rosters
)

from cbs_get_league import get_cbs_teams, get_cbs_roster

initialize_database()

# ------------------
# CONFIG
# ------------------

LEAGUE_ID = 465649962  # replace with your league ID
YEAR = 2026
SWID = "{E8418BEB-2939-480F-818B-EB2939E80F06}"
ESPN_S2 = "AEAtk3BaOcADlcYivYJmH7p2BvHMp4vpKCmVn%2B6aucUeZN3pYFIeecyM%2Fst66dXM0tvd9%2FMudnDZva8KkNLrB57N1sMa0MaVtOybvbSe8OdIf3SWLuB9Hzk5UQI7LeHOUVj2lQVEwSa6Q%2F85csfri%2FlU8RIc5gTNfkkrZzLbI2L8owzcUKxYwxPSuHI%2FKlBwx9ji%2BXJahc3FfVKI0UCZ2jNmKjJc37FzQ7z1qqxL5RQrwFHHks4gS1qrrrpvKwOZGDBNNPCR9Q3lzdV7lI4uQkTfmo%2Bw7%2FaoyQ74%2FPxj%2FmHtl2V6PZ1%2FsltH6TcZ65k7SS%2FuKk1nQsW0vislxG61jELHQ%2FbcAAYwxMGWVz35AOvRe0hYAXGz8Ie707pcgXCic1M%3D"


# ------------------
# LOAD LEAGUE
# ------------------

@st.cache_resource
def load_league():
    return League(
        league_id=LEAGUE_ID,
        year=YEAR,
        swid=SWID,
        espn_s2=ESPN_S2
    )

league = load_league()
save_league_snapshot(league)
save_rosters(league)

# ------------------
# PAGE
# ------------------

st.set_page_config(
    page_title="Fantasy Command Center",
    layout="wide"
)

st.title("🏈 Fantasy Command Center")

st.subheader(league.settings.name)


# ------------------
# STANDINGS
# ------------------

rows = []

for team in league.teams:
    rows.append({
        "Team": team.team_name,
        "Wins": team.wins,
        "Losses": team.losses,
        "Points For": round(team.points_for, 2)
    })

df = pd.DataFrame(rows)

df = df.sort_values(
    ["Wins", "Points For"],
    ascending=False
)

st.header("Standings")

st.dataframe(
    df,
    use_container_width=True
)


st.header("Team Rosters")

# ESPN teams
espn_rows = []

for team in league.teams:
    espn_rows.append({
        "platform": "ESPN",
        "provider_team_id": str(team.team_id),
        "team_name": team.team_name
    })

espn_df = pd.DataFrame(espn_rows)

# CBS teams
cbs_df = get_cbs_teams()

cbs_df["platform"] = "CBS"


# Unified selector
league_options = pd.concat(
    [espn_df, cbs_df],
    ignore_index=True
)

league_options["label"] = (
    league_options["platform"]
    + " | "
    + league_options["team_name"]
)

selected_label = st.selectbox(
    "Choose Team",
    league_options["label"]
)

selected = league_options[
    league_options["label"] == selected_label
].iloc[0]

# Before using team_obj, ensure it is defined for both ESPN and CBS cases
#st.write(league_options.columns.tolist())

team_obj = None

if selected["platform"] == "ESPN":

    team_obj = next(
        (
            t for t in league.teams
            if str(t.team_id) == str(selected["provider_team_id"])
        ),
        None
    )

    if team_obj is None:
        st.error("ESPN team not found.")
        st.stop()

    roster_rows = []

    for player in team_obj.roster:
        roster_rows.append({
            "Player": player.name,
            "Position": player.position
        })

    roster_df = pd.DataFrame(roster_rows)

else:

    roster_df = get_cbs_roster(
        selected["provider_team_id"]
    )

    roster_df.rename(
        columns={
            "player_name": "Player",
            "position": "Position"
        },
        inplace=True
    )

st.dataframe(
    roster_df,
    use_container_width=True
)

if team_obj is not None:
    current_lineup = []

    for player in team_obj.roster:
        slot = getattr(player, "lineupSlot", "BE")

        if slot in {"BE", "IR"}:
            continue

        current_lineup.append({
            "Slot": slot,
            "Player": player.name,
            "Position": player.position,
            "Score": round(calculate_player_score(player), 2)
        })

    POSITION_PRIORITY = [
        "QB",
        "RB",
        "WR",
        "TE",
        "RB/WR/TE",
        "K",
        "DST",
        "DL",
        "LB",
        "DB"
    ]

    def slot_order(slot):
        normalized = "".join(
            c for c in slot
            if not c.isdigit()
        )

        try:
            return POSITION_PRIORITY.index(normalized)
        except ValueError:
            return 999

    current_lineup = sorted(current_lineup, key=lambda x: slot_order(x["Slot"]))

    current_df = pd.DataFrame(current_lineup)

if team_obj is not None:

    lineup, projected_total = get_optimal_lineup(team_obj)

    optimized_rows = lineup_to_dataframe(lineup)
    optimized_df = pd.DataFrame(optimized_rows)
    optimized_df = optimized_df.sort_values(by="Slot", key=lambda col: [POSITION_PRIORITY.index(s) if s in POSITION_PRIORITY else 999 for s in col])

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"Current Lineup ({get_current_lineup_score(team_obj):.1f})")
        st.table(current_df)

    with col2:
        st.subheader(f"Optimized Lineup ({projected_total:.1f})")
        st.table(optimized_df)

    slots = sorted(
        list(
            set(
                getattr(p, "lineupSlot", "BE")
                for p in team_obj.roster
            )
        )
    )

    st.write("Roster Slots:", slots)

    positions = sorted(
        list(
            set(
                p.position
                for p in team_obj.roster
            )
        )
    )

    st.write("Roster Positions:", positions)
    current_score = get_current_lineup_score(team_obj)
    potential_gain = projected_total - current_score

else:
    st.info(
        "CBS roster loaded successfully. "
        "Lineup optimizer and advanced metrics are currently available for ESPN teams only."
    )