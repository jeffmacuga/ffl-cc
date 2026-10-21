import unicodedata

import pandas as pd
import streamlit as st

from config import LEAGUES
from optimizer import get_optimal_lineup, lineup_to_dataframe
from pages.standings import get_cbs_team_options, load_espn_league
from services.cbs_lineup_optimizer import optimize_cbs_lineup
from services.cbs_lineup_submission import (
    CBSLineupError,
    apply_confirmed_lineup,
    fetch_cbs_team_roster,
    fetch_my_cbs_roster,
)
from services.projection_comparison import (
    add_projection_columns,
    append_projection_totals,
    build_cbs_projection_lookup,
    build_espn_optimized_projection_lookup,
    load_cbs_projection_lookup,
)


ESPN_PROJECTION_COLUMN_NAMES = {
    "Kick-Butt Football": "KickButt Optimized Projection",
    "AFS": "AFS Optimized Projection",
}


def _find_espn_owned_team(league, swid):
    owner_id = str(swid).strip().strip("{}").casefold()
    return next(
        (
            team
            for team in league.teams
            if any(
                str(owner.get("id") or "").strip().strip("{}").casefold()
                == owner_id
                for owner in team.owners
            )
        ),
        None,
    )


def _style_total_row(row):
    style = "color: #007FFF; font-weight: bold"
    return [style if row.get("Player") == "Total" else "" for _ in row]


def _normalize_name_for_lookup(value):
    normalized = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _round_projection_columns(frame, columns=None):
    rounded = frame.copy()
    target_columns = columns or [
        column
        for column in rounded.columns
        if column.lower().endswith("projection")
        or column.lower().endswith("points")
        or column.lower() == "score"
    ]
    for column in target_columns:
        if column in rounded.columns:
            rounded[column] = pd.to_numeric(rounded[column], errors="coerce").round(2)
    return rounded


def _projection_column_config(columns):
    return {
        column: st.column_config.NumberColumn(format="%.2f")
        for column in columns
    }


def _add_bye_week_column(frame, player_records, player_column="Player"):
    if frame.empty or not player_records:
        return frame

    bye_lookup = {}
    for player in player_records:
        name = (
            player.get("player_name")
            if isinstance(player, dict)
            else getattr(player, "player_name", None)
        )
        if name is None:
            name = (
                player.get("name")
                if isinstance(player, dict)
                else getattr(player, "name", None)
            )
        bye_week = (
            player.get("bye_week")
            if isinstance(player, dict)
            else getattr(player, "bye_week", None)
        )
        if name is None or bye_week is None:
            continue
        bye_lookup[_normalize_name_for_lookup(name)] = bye_week

    with_bye_weeks = frame.copy()
    with_bye_weeks["Bye Week"] = with_bye_weeks[player_column].map(
        lambda player_name: bye_lookup.get(
            _normalize_name_for_lookup(player_name), ""
        )
    )
    return with_bye_weeks


def _load_espn_projection_lookups(
    current_league_name=None,
    current_league=None,
):
    projection_lookups = {}
    for league_config in LEAGUES:
        if league_config["platform"] != "ESPN":
            continue
        league = (
            current_league
            if current_league is not None
            and league_config["name"] == current_league_name
            else load_espn_league(league_config)
        )
        projection_lookups[
            ESPN_PROJECTION_COLUMN_NAMES[league_config["name"]]
        ] = build_espn_optimized_projection_lookup(league)
    return projection_lookups


def show_espn_lineup_preview(selected_league):
    league = load_espn_league(selected_league)
    teams_by_id = {str(team.team_id): team for team in league.teams}
    owned_team = _find_espn_owned_team(league, selected_league["swid"])
    if (
        st.session_state.get("espn_lineup_preview_league")
        != selected_league["name"]
    ):
        if owned_team is not None:
            st.session_state["espn_lineup_preview_team"] = str(
                owned_team.team_id
            )
        else:
            st.session_state.pop("espn_lineup_preview_team", None)
        st.session_state["espn_lineup_preview_league"] = selected_league["name"]
    elif st.session_state.get("espn_lineup_preview_team") not in teams_by_id:
        st.session_state["espn_lineup_preview_team"] = str(
            owned_team.team_id
            if owned_team is not None
            else next(iter(teams_by_id))
        )
    if owned_team is None:
        st.warning(
            "Could not match the authenticated ESPN account to a team in "
            "this league; select your team from the list."
        )
    team_id = st.selectbox(
        "Team to preview",
        options=list(teams_by_id),
        format_func=lambda value: teams_by_id[value].team_name,
        key="espn_lineup_preview_team",
    )
    selected_team = teams_by_id[team_id]
    st.write(f"Optimal lineup for **{selected_team.team_name}**")
    st.caption(
        "The lineup uses this ESPN league's optimized projections. The "
        "aggregate is the mean of available projections from KickButt, AFS, "
        "and CBS. Player matches use normalized names."
    )
    optimal_lineup = get_optimal_lineup(selected_team)
    if isinstance(optimal_lineup, tuple):
        optimal_lineup = optimal_lineup[0]
    lineup_df = pd.DataFrame(lineup_to_dataframe(optimal_lineup))[
        ["Slot", "Player"]
    ]
    projection_lookups = _load_espn_projection_lookups(
        current_league_name=selected_league["name"],
        current_league=league,
    )
    projection_lookups["CBS Optimized Projection"] = load_cbs_projection_lookup()
    lineup_df = add_projection_columns(lineup_df, projection_lookups)
    selected_column = ESPN_PROJECTION_COLUMN_NAMES[selected_league["name"]]
    total_columns = [
        selected_column,
        "CBS Optimized Projection",
        "Aggregate Projection",
    ]
    lineup_df = append_projection_totals(lineup_df, total_columns)
    display_df = lineup_df[["Slot", "Player", *total_columns]]
    display_df = _add_bye_week_column(display_df, selected_team.roster)
    display_df = _round_projection_columns(display_df)
    display_df = display_df[["Slot", "Player", "Bye Week", *total_columns]]
    st.dataframe(
        display_df.style.apply(_style_total_row, axis=1),
        column_config=_projection_column_config(total_columns),
        use_container_width=True,
        hide_index=True,
    )


def show_cbs_lineup_preview():
    st.caption(
        "Choose a CBS team for a live lineup preview. Your authenticated team "
        "can be submitted only after explicit confirmation."
    )
    authenticated_team = st.session_state.get("cbs_authenticated_team")
    authenticated_roster = None
    if authenticated_team is None:
        try:
            authenticated_roster = fetch_my_cbs_roster()
        except CBSLineupError as exc:
            st.error(str(exc))
            return
        authenticated_team = {
            "team_id": str(authenticated_roster["team_id"]),
            "team_name": str(authenticated_roster["team_name"]),
        }
        st.session_state["cbs_authenticated_team"] = authenticated_team

    cbs_team_options = get_cbs_team_options()
    team_names_by_id = dict(cbs_team_options)
    authenticated_team_id = authenticated_team["team_id"]
    if authenticated_team_id not in team_names_by_id:
        team_names_by_id[authenticated_team_id] = authenticated_team[
            "team_name"
        ]
    if st.session_state.get("cbs_preview_team") not in team_names_by_id:
        st.session_state["cbs_preview_team"] = authenticated_team_id

    selected_preview_team = st.selectbox(
        "Team to preview",
        options=list(team_names_by_id),
        format_func=lambda team_id: (
            f"{team_names_by_id[team_id]} (your team)"
            if team_id == authenticated_team_id
            else team_names_by_id[team_id]
        ),
        key="cbs_preview_team",
    )
    preview = st.session_state.get("cbs_lineup_preview")
    if (
        preview is None
        or preview.get("preview_requested_team") != selected_preview_team
    ):
        try:
            if selected_preview_team == authenticated_team_id:
                live_roster = authenticated_roster or fetch_my_cbs_roster()
            else:
                live_roster = fetch_cbs_team_roster(selected_preview_team)
            projection_lookups = _load_espn_projection_lookups()
            projection_lookups["CBS Optimized Projection"] = (
                build_cbs_projection_lookup(live_roster["players"])
            )
            result = optimize_cbs_lineup(
                live_roster["players"],
                allow_average_fallback=False,
            )
            st.session_state["cbs_lineup_preview"] = {
                **live_roster,
                "result": result,
                "projection_lookups": projection_lookups,
                "can_submit": selected_preview_team == authenticated_team_id,
                "preview_requested_team": selected_preview_team,
            }
        except CBSLineupError as exc:
            st.error(str(exc))
            return

    preview = st.session_state.get("cbs_lineup_preview")
    if not preview:
        st.info("Select a CBS team to build a live lineup preview.")
        return

    st.write(
        f"**{preview['team_name']}** — CBS week {preview['week']} "
        f"(CBS lineup status: {preview['lineup_status'] or 'unknown'})"
    )
    st.caption(
        "The lineup and submission proposal use CBS projections. The "
        "aggregate is the mean of available projections from KickButt, AFS, "
        "and CBS. Player matches use normalized names."
    )
    result = preview["result"]
    if not result["complete"]:
        st.warning(
            "The current CBS lineup status does not block optimization. "
            "However, the roster does not have an eligible player for every "
            "required starter slot, so a complete proposal cannot be prepared."
        )
        if result["missing_slots"]:
            st.error(
                "No rostered eligible player is available for: "
                + ", ".join(result["missing_slots"])
            )
        return

    lineup_df = pd.DataFrame(result["lineup"]).rename(
        columns={"slot": "Slot", "player": "Player"}
    )[["Slot", "Player"]]
    lineup_df = add_projection_columns(
        lineup_df,
        preview["projection_lookups"],
    )
    total_columns = [
        "CBS Optimized Projection",
        "KickButt Optimized Projection",
        "Aggregate Projection",
    ]
    lineup_df = append_projection_totals(lineup_df, total_columns)
    display_df = lineup_df[["Slot", "Player", *total_columns]]
    display_df = _add_bye_week_column(display_df, preview["players"])
    display_df = _round_projection_columns(display_df)
    display_df = display_df[["Slot", "Player", "Bye Week", *total_columns]]
    st.dataframe(
        display_df.style.apply(_style_total_row, axis=1),
        column_config=_projection_column_config(total_columns),
        use_container_width=True,
        hide_index=True,
    )

    if result["missing_projection_count"]:
        st.warning(
            f"{result['missing_projection_count']} available player(s) have "
            "no CBS projection and are scored as 0.0 by the CBS optimizer."
        )
    if result["zero_projection_count"]:
        st.warning(
            f"{result['zero_projection_count']} available player(s) have "
            "a 0.0 CBS projection; this can indicate a bye or unavailable "
            "projection, so verify before using the preview."
        )

    can_submit = preview.get("can_submit", False)
    st.subheader(
        "Suggested changes (CBS projections only)"
        if can_submit
        else "Suggested lineup changes (CBS projections only; preview only)"
    )
    if not result["moves"]:
        st.success("The optimized lineup already matches the active lineup.")
        return

    moves_df = pd.DataFrame(result["moves"]).rename(
        columns={
            "player": "Player",
            "position": "Position",
            "current_assignment": "Current Assignment",
            "suggested_assignment": "Suggested Assignment",
            "projected_points": "Projected Points",
        }
    )
    if "Projected Points" in moves_df.columns:
        moves_df["Projected Points"] = pd.to_numeric(
            moves_df["Projected Points"], errors="coerce"
        ).round(2)
    st.dataframe(
        moves_df,
        column_config=_projection_column_config(["Projected Points"]),
        use_container_width=True,
        hide_index=True,
    )

    if not can_submit:
        st.info(
            "This is another team's roster. The suggested lineup is "
            "read-only and cannot be submitted."
        )
        return

    locked_moves = [
        move for move in result["moves"]
        if move["is_locked"] is not None
        and str(move["is_locked"]).strip().lower()
        in {"1", "true", "yes", "locked"}
    ]
    unknown_lock_moves = [
        move for move in result["moves"]
        if move["is_locked"] is None
    ]
    if locked_moves:
        st.error(
            "CBS reports one or more proposed players as locked. "
            "No changes can be submitted."
        )
    if unknown_lock_moves:
        st.error(
            "CBS did not provide lock status for every proposed player. "
            "No changes can be submitted."
        )

    st.warning(
        "Submitting changes immediately updates your CBS lineup. "
        "Review every move; locked players and stale previews are rejected."
    )
    confirmation = st.checkbox(
        f"I reviewed these changes for {preview['team_name']} in week "
        f"{preview['week']} and want to submit them to CBS.",
        key=f"cbs_confirm_{preview['fingerprint']}",
    )
    submit_disabled = (
        not confirmation or bool(locked_moves) or bool(unknown_lock_moves)
    )
    if st.button(
        "Submit confirmed lineup changes to CBS",
        key=f"cbs_submit_{preview['fingerprint']}",
        disabled=submit_disabled,
    ):
        try:
            apply_confirmed_lineup(
                expected_fingerprint=preview["fingerprint"],
                team_id=preview["team_id"],
                week=preview["week"],
                moves=result["moves"],
            )
            st.session_state.pop("cbs_lineup_preview", None)
            st.success(
                "CBS lineup changes were submitted and verified. "
                "Refresh the live lineup to see the updated roster."
            )
        except CBSLineupError as exc:
            st.error(str(exc))


def show_lineup_preview(selected_league, selected_league_name):
    st.header("Lineup Preview")
    if selected_league["platform"] == "ESPN":
        show_espn_lineup_preview(selected_league)
    elif selected_league["platform"] == "CBS":
        show_cbs_lineup_preview()
    else:
        st.info("Lineup previews are not available for this platform yet.")
