import math
from collections import Counter
from types import SimpleNamespace

import pandas as pd

from optimizer import get_optimal_lineup, lineup_to_dataframe, normalize_position


PLAYER_COLUMNS = {"player_id", "player_name", "position", "projected_points"}


def _projection(value):
    try:
        projection = float(value)
    except (TypeError, ValueError):
        return None
    return projection if math.isfinite(projection) else None


def _select_players(roster, player_ids):
    missing_columns = PLAYER_COLUMNS - set(roster.columns)
    if missing_columns:
        raise ValueError(
            "Roster is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    keyed_players = {}
    for _, player in roster.iterrows():
        player_id = str(player["player_id"])
        if player_id in keyed_players:
            raise ValueError(f"Roster contains duplicate player ID: {player_id}")
        keyed_players[player_id] = player

    selected = []
    for player_id in player_ids:
        player_id = str(player_id)
        if player_id not in keyed_players:
            raise ValueError(f"Selected player is not on the roster: {player_id}")
        selected.append(keyed_players[player_id])
    return selected


def _position_impact(roster, sent_players, received_players, roster_requirements):
    before = Counter(
        normalize_position(position)
        for position in roster["position"]
        if pd.notna(position)
    )
    after = before.copy()

    for player in sent_players:
        position_value = player["position"]
        position = (
            normalize_position(position_value)
            if pd.notna(position_value)
            else ""
        )
        if position:
            after[position] -= 1
    for player in received_players:
        position_value = player["position"]
        position = (
            normalize_position(position_value)
            if pd.notna(position_value)
            else ""
        )
        if position:
            after[position] += 1

    positions = sorted(set(before) | set(after) | set(roster_requirements))
    return pd.DataFrame([
        {
            "Position": position,
            "Before": before[position],
            "After": after[position],
            "Change": after[position] - before[position],
            "Fixed starting slots": roster_requirements.get(position),
        }
        for position in positions
    ])


def _projection_total(players):
    projections = [_projection(player["projected_points"]) for player in players]
    available = [value for value in projections if value is not None]
    return sum(available), len(projections) - len(available)


def _optimizer_team(roster):
    players = []
    for _, player in roster.iterrows():
        projection = _projection(player["projected_points"]) or 0
        players.append(SimpleNamespace(
            id=str(player["player_id"]),
            name=player["player_name"],
            position=normalize_position(player["position"]),
            projected_avg_points=projection,
            projected_points=0,
            avg_points=0,
            injuryStatus=player.get("injury_status", ""),
        ))
    return SimpleNamespace(roster=players)


def _lineup_summary(roster, lineup_requirements):
    lineup, projection = get_optimal_lineup(
        _optimizer_team(roster),
        lineup_requirements=lineup_requirements,
        allow_average_fallback=False,
    )
    return {
        "projection": projection,
        "players": pd.DataFrame(lineup_to_dataframe(lineup)),
    }


def _post_trade_roster(roster, sent_ids, received_players):
    retained = roster[
        ~roster["player_id"].astype(str).isin({str(player_id) for player_id in sent_ids})
    ]
    return pd.concat(
        [retained, pd.DataFrame(received_players)],
        ignore_index=True,
    )


def analyze_trade(
    your_roster,
    partner_roster,
    your_player_ids,
    partner_player_ids,
    roster_requirements=None,
    lineup_requirements=None,
):
    """Compare projected points and position changes for a proposed trade."""
    roster_requirements = roster_requirements or {}
    your_players = _select_players(your_roster, your_player_ids)
    partner_players = _select_players(partner_roster, partner_player_ids)

    your_sending, your_missing = _projection_total(your_players)
    your_receiving, your_receiving_missing = _projection_total(partner_players)
    partner_sending, partner_missing = _projection_total(partner_players)
    partner_receiving, partner_receiving_missing = _projection_total(your_players)

    result = {
        "your_side": {
            "sent_projection": your_sending,
            "received_projection": your_receiving,
            "net_projection": your_receiving - your_sending,
            "missing_projections": your_missing + your_receiving_missing,
            "position_impact": _position_impact(
                your_roster,
                your_players,
                partner_players,
                roster_requirements,
            ),
        },
        "partner_side": {
            "sent_projection": partner_sending,
            "received_projection": partner_receiving,
            "net_projection": partner_receiving - partner_sending,
            "missing_projections": partner_missing + partner_receiving_missing,
            "position_impact": _position_impact(
                partner_roster,
                partner_players,
                your_players,
                roster_requirements,
            ),
        },
    }

    if lineup_requirements is not None:
        your_after_roster = _post_trade_roster(
            your_roster,
            your_player_ids,
            partner_players,
        )
        partner_after_roster = _post_trade_roster(
            partner_roster,
            partner_player_ids,
            your_players,
        )
        for side, before_roster, after_roster in (
            ("your_side", your_roster, your_after_roster),
            ("partner_side", partner_roster, partner_after_roster),
        ):
            before = _lineup_summary(before_roster, lineup_requirements)
            after = _lineup_summary(after_roster, lineup_requirements)
            result[side]["lineup_impact"] = {
                "before_projection": before["projection"],
                "after_projection": after["projection"],
                "change": after["projection"] - before["projection"],
                "before_lineup": before["players"],
                "after_lineup": after["players"],
            }

    return result
