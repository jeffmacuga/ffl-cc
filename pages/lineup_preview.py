import unicodedata

import pandas as pd
import streamlit as st
from espn_api.football.constant import POSITION_MAP

from config import LEAGUES
from pages.standings import get_cbs_team_options, load_espn_league
from services.cbs_lineup_optimizer import (
    is_player_locked,
    is_player_unlocked,
    optimize_cbs_lineup,
)
from services.database import format_last_data_sync, format_sync_timestamp
from services.cbs_lineup_submission import (
    CBSLineupError,
    apply_confirmed_lineup,
    fetch_cbs_team_roster,
    fetch_my_cbs_roster,
)
from services.espn_lineup_submission import (
    ESPNLineupSubmissionError,
    apply_confirmed_espn_lineup,
    build_espn_lineup_proposal,
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
AFS_LINEUP_SLOT_ORDER = (
    "QB",
    "RB",
    "WR",
    "TE",
    "RB/WR/TE",
    "K",
    "D/ST",
)
KICKBUTT_LINEUP_SLOT_ORDER = (
    "QB",
    "RB",
    "WR",
    "TE",
    "RB/WR/TE",
    "K",
    "DL",
    "LB",
    "DB",
)


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


def _sort_espn_lineup_preview(frame, slot_order):
    slot_order = {
        slot: index for index, slot in enumerate(slot_order)
    }
    return (
        frame.assign(
            _slot_order=frame["Slot"].map(slot_order).fillna(len(slot_order))
        )
        .sort_values("_slot_order", kind="stable")
        .drop(columns="_slot_order")
        .reset_index(drop=True)
    )


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
    st.caption(format_last_data_sync("ESPN", selected_league["name"]))
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
    can_submit = (
        owned_team is not None
        and str(selected_team.team_id) == str(owned_team.team_id)
    )
    proposal = None
    proposal_error = None
    try:
        proposal = build_espn_lineup_proposal(league, selected_team)
    except ESPNLineupSubmissionError as exc:
        proposal_error = exc

    st.write(f"Optimal lineup for **{selected_team.team_name}**")
    st.caption(
        "The lineup uses this ESPN league's optimized projections. The "
        "aggregate is the mean of available projections from KickButt, AFS, "
        "and CBS. Player matches use normalized names."
    )
    if proposal_error is not None:
        st.error(str(proposal_error))
        return

    assert proposal is not None
    slot_names = {
        slot_id: slot_name
        for slot_id, slot_name in POSITION_MAP.items()
        if isinstance(slot_id, int) and slot_name
    }
    reserve_slots = {
        slot_id
        for slot_id, slot_name in slot_names.items()
        if slot_name in {"BE", "IR", "ER", "Rookie"}
    }
    lineup_df = pd.DataFrame([
        {
            "Slot": slot_names.get(slot_id, str(slot_id)),
            "Player": player.name,
        }
        for player in selected_team.roster
        if (
            slot_id := proposal["expected_slots"][
                int(player.playerId)
            ]
        ) not in reserve_slots
    ])
    if selected_league["name"] == "AFS":
        lineup_df = _sort_espn_lineup_preview(
            lineup_df,
            AFS_LINEUP_SLOT_ORDER,
        )
    elif selected_league["name"] == "Kick-Butt Football":
        lineup_df = _sort_espn_lineup_preview(
            lineup_df,
            KICKBUTT_LINEUP_SLOT_ORDER,
        )
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

    if not can_submit:
        st.info(
            "Lineup changes can only be submitted for the authenticated "
            "ESPN account's team."
        )
        return

    if not proposal["changes"]:
        st.success("The optimized lineup already matches the active lineup.")
        return

    player_names = {
        int(player.playerId): player.name
        for player in selected_team.roster
    }
    moves_df = pd.DataFrame([
        {
            "Player": player_names.get(move["playerId"], "Unknown player"),
            "Current Assignment": slot_names.get(
                move["fromLineupSlotId"],
                str(move["fromLineupSlotId"]),
            ),
            "Suggested Assignment": slot_names.get(
                move["toLineupSlotId"],
                str(move["toLineupSlotId"]),
            ),
        }
        for move in proposal["changes"]
    ])
    st.subheader("Suggested lineup changes")
    st.dataframe(moves_df, use_container_width=True, hide_index=True)
    st.warning(
        "Submitting immediately updates your ESPN lineup. Players whose "
        "games have started and stale previews are rejected; review every "
        "move before continuing."
    )
    confirmation_key = (
        f"espn_confirm_{selected_league['name']}_{proposal['team_id']}_"
        f"{proposal['fingerprint']}"
    )
    confirmation = st.checkbox(
        f"I reviewed these changes for {selected_team.team_name} and want "
        "to submit them to ESPN.",
        key=confirmation_key,
    )
    if st.button(
        "Submit confirmed lineup changes to ESPN",
        key=f"espn_submit_{selected_league['name']}_{proposal['team_id']}",
        disabled=not confirmation,
    ):
        try:
            apply_confirmed_espn_lineup(
                selected_league,
                proposal["team_id"],
                proposal["fingerprint"],
                proposal["expected_slots"],
                proposal["changes"],
            )
            st.success(
                "ESPN lineup changes were submitted and verified. "
                "Refresh the preview to see the updated lineup."
            )
        except ESPNLineupSubmissionError as exc:
            st.error(str(exc))


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
    st.caption(format_sync_timestamp(preview["synced_at"]))
    st.caption(
        "The lineup and submission proposal use CBS projections. The "
        "aggregate is the mean of available projections from KickButt, AFS, "
        "and CBS. Player matches use normalized names."
    )
    result = preview["result"]
    if not result["complete"]:
        st.warning(
            "The current CBS lineup status does not block optimization. "
            "However, the available roster cannot fill every required "
            "starter slot, so a complete proposal cannot be prepared."
        )
        if result["missing_slots"]:
            st.error(
                "Rostered eligible players cannot fill: "
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
        if is_player_locked(move["is_locked"])
    ]
    unknown_lock_moves = [
        move for move in result["moves"]
        if not is_player_locked(move["is_locked"])
        and not is_player_unlocked(move["is_locked"])
    ]
    if locked_moves:
        st.error(
            "CBS reports one or more proposed players as locked. "
            "No changes can be submitted."
        )
    if unknown_lock_moves:
        st.error(
            "CBS did not provide a recognized unlocked status for every "
            "proposed player. "
            "No changes can be submitted."
        )

    st.info(
        "CBS-locked players and players without an explicit unlocked status "
        "are held in their current assignments. Only unlocked players are "
        "included in the proposed changes."
    )
    st.warning(
        "Submitting changes immediately updates your CBS lineup. "
        "Review every move; stale previews are rejected."
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
