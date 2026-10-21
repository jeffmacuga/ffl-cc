"""Read-only lineup optimization using the CBS roster slots observed in the league."""

import json
import math
from functools import lru_cache


LINEUP_SLOTS = (
    ("QB", "QB"),
    ("RB1", "RB"),
    ("RB2", "RB"),
    ("WR-TE1", "WR-TE"),
    ("WR-TE2", "WR-TE"),
    ("WR-TE3", "WR-TE"),
    ("RB-WR-TE", "RB-WR-TE"),
    ("K", "K"),
    ("DST", "DST"),
)

SLOT_ELIGIBILITY = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR-TE": {"WR", "TE"},
    "RB-WR-TE": {"RB", "WR", "TE"},
    "K": {"K"},
    "DST": {"DST"},
}

POSITION_ALIASES = {
    "DEF": "DST",
    "D/ST": "DST",
}
INJURED_STATUSES = {"I", "IR", "INJ", "INJURED"}


def _positions(value, fallback):
    if value is None:
        values = []
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        text = str(value).strip()
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            decoded = text
        values = decoded if isinstance(decoded, list) else [decoded]

    positions = set()
    for item in values:
        text = str(item).strip().upper()
        if text in POSITION_ALIASES:
            positions.add(POSITION_ALIASES[text])
            continue
        for position in text.replace("/", "-").replace(",", "-").split("-"):
            position = position.strip()
            if position:
                positions.add(POSITION_ALIASES.get(position, position))

    if not positions and fallback:
        position = str(fallback).strip().upper()
        positions.add(POSITION_ALIASES.get(position, position))
    return positions


def _projection(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if math.isfinite(score) else None


def _player_score(player, allow_average_fallback):
    projection = _projection(player.get("projected_points"))
    if allow_average_fallback and (projection is None or projection <= 0):
        average_points = _projection(
            player.get("average_points")
            if player.get("average_points") is not None
            else player.get("avg_points")
        )
        if average_points is not None and average_points > 0:
            return average_points
    return projection if projection is not None else 0.0


def _current_assignment(player):
    status = str(player.get("roster_status") or "").strip().upper()
    if status in INJURED_STATUSES:
        return "Injured"
    if status == "A":
        return str(player.get("roster_position") or "Starter")
    return "Bench"


def optimize_cbs_lineup(roster, allow_average_fallback=False):
    """Return a maximum-projection legal lineup and the moves needed to reach it."""
    candidates = []
    missing_projection_count = 0
    zero_projection_count = 0
    average_fallback_count = 0

    for player in roster:
        if str(player.get("roster_status") or "").strip().upper() in INJURED_STATUSES:
            continue

        projection = _projection(player.get("projected_points"))
        if projection is None:
            missing_projection_count += 1
        elif projection == 0:
            zero_projection_count += 1

        score = _player_score(player, allow_average_fallback)
        average_points = _projection(
            player.get("average_points")
            if player.get("average_points") is not None
            else player.get("avg_points")
        )
        if (
            allow_average_fallback
            and (projection is None or projection <= 0)
            and average_points is not None
            and average_points > 0
        ):
            average_fallback_count += 1

        position = player.get("position")
        eligible_positions = _positions(
            player.get("eligible_positions"),
            position,
        )
        candidates.append({
            "player_id": str(player.get("provider_player_id", player.get("player_name"))),
            "name": str(player.get("player_name") or "Unknown player"),
            "position": str(position or ""),
            "eligible_positions": eligible_positions,
            "score": score,
            "roster_status": str(player.get("roster_status") or "").strip().upper(),
            "roster_position": str(player.get("roster_position") or ""),
            "is_locked": player.get("is_locked"),
        })

    if not candidates:
        return {
            "lineup": [],
            "moves": [],
            "missing_slots": [slot_name for slot_name, _ in LINEUP_SLOTS],
            "projected_points": 0.0,
            "current_projected_points": 0.0,
            "improvement": 0.0,
            "missing_projection_count": missing_projection_count,
            "zero_projection_count": zero_projection_count,
            "average_fallback_count": average_fallback_count,
            "complete": False,
        }

    slot_options = []
    missing_slots = []
    for slot_name, slot_type in LINEUP_SLOTS:
        accepted_positions = SLOT_ELIGIBILITY[slot_type]
        eligible_players = tuple(
            index
            for index, player in enumerate(candidates)
            if player["eligible_positions"] & accepted_positions
        )
        slot_options.append((slot_name, slot_type, eligible_players))
        if not eligible_players:
            missing_slots.append(slot_name)

    slot_options.sort(key=lambda item: (len(item[2]), item[0]))

    if missing_slots:
        return {
            "lineup": [],
            "moves": [],
            "missing_slots": missing_slots,
            "projected_points": 0.0,
            "current_projected_points": sum(
                _player_score(player, allow_average_fallback)
                for player in roster
                if str(player.get("roster_status") or "").strip().upper() == "A"
            ),
            "improvement": 0.0,
            "missing_projection_count": missing_projection_count,
            "zero_projection_count": zero_projection_count,
            "average_fallback_count": average_fallback_count,
            "complete": False,
        }

    @lru_cache(maxsize=None)
    def best_assignment(slot_index, used_players):
        if slot_index == len(slot_options):
            return 0.0, ()

        best_score = float("-inf")
        best_players = ()
        for player_index in slot_options[slot_index][2]:
            player_mask = 1 << player_index
            if used_players & player_mask:
                continue

            remaining_score, remaining_players = best_assignment(
                slot_index + 1,
                used_players | player_mask,
            )
            if remaining_score == float("-inf"):
                continue

            score = candidates[player_index]["score"] + remaining_score
            assignment = (player_index,) + remaining_players
            if score > best_score or (
                score == best_score and assignment < best_players
            ):
                best_score = score
                best_players = assignment

        return best_score, best_players

    optimal_score, assignment = best_assignment(0, 0)
    if optimal_score == float("-inf"):
        return {
            "lineup": [],
            "moves": [],
            "missing_slots": [],
            "projected_points": 0.0,
            "current_projected_points": sum(
                _player_score(player, allow_average_fallback)
                for player in roster
                if str(player.get("roster_status") or "").strip().upper() == "A"
            ),
            "improvement": 0.0,
            "missing_projection_count": missing_projection_count,
            "zero_projection_count": zero_projection_count,
            "average_fallback_count": average_fallback_count,
            "complete": False,
        }

    lineup = []
    selected_assignments = {}
    for (slot_name, slot_type, _), player_index in zip(slot_options, assignment):
        player = candidates[player_index]
        selected_assignments[player["player_id"]] = slot_type
        lineup.append({
            "slot": slot_name,
            "player_id": player["player_id"],
            "player": player["name"],
            "position": player["position"],
            "projected_points": player["score"],
            "current_assignment": _current_assignment(player),
        })

    slot_groups = dict.fromkeys(slot_type for _, slot_type in LINEUP_SLOTS)
    for slot_type in slot_groups:
        slot_names = [
            slot_name
            for slot_name, candidate_type in LINEUP_SLOTS
            if candidate_type == slot_type
        ]
        group = sorted(
            (row for row in lineup if row["slot"] in slot_names),
            key=lambda row: (-row["projected_points"], row["player"].casefold()),
        )
        for slot_name, row in zip(slot_names, group):
            row["slot"] = slot_name

    slot_order = {
        slot_name: index
        for index, (slot_name, _) in enumerate(LINEUP_SLOTS)
    }
    lineup.sort(key=lambda row: slot_order[row["slot"]])

    moves = []
    for player in candidates:
        proposed_assignment = selected_assignments.get(player["player_id"], "Bench")
        current_status = player["roster_status"]
        current_slot_type = player["roster_position"].upper()
        is_current_starter = current_status == "A"
        unchanged = (
            is_current_starter and current_slot_type == proposed_assignment
        ) or (
            not is_current_starter
            and proposed_assignment == "Bench"
            and current_status not in INJURED_STATUSES
        )
        if unchanged:
            continue

        moves.append({
            "player_id": player["player_id"],
            "player": player["name"],
            "position": player["position"],
            "current_assignment": _current_assignment(player),
            "suggested_assignment": proposed_assignment,
            "suggested_roster_position": (
                player["roster_position"]
                if proposed_assignment == "Bench"
                else proposed_assignment
            ),
            "projected_points": player["score"],
            "is_locked": player["is_locked"],
        })

    current_score = sum(
        _player_score(player, allow_average_fallback)
        for player in roster
        if str(player.get("roster_status") or "").strip().upper() == "A"
    )

    return {
        "lineup": lineup,
        "moves": moves,
        "missing_slots": [],
        "projected_points": optimal_score,
        "current_projected_points": current_score,
        "improvement": optimal_score - current_score,
        "missing_projection_count": missing_projection_count,
        "zero_projection_count": zero_projection_count,
        "average_fallback_count": average_fallback_count,
        "complete": True,
    }
