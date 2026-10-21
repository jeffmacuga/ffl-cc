# optimizer.py
from itertools import combinations
from collections import defaultdict

POSITION_MAP = {
    "QB": ["QB"],
    "RB": ["RB"],
    "WR": ["WR"],
    "TE": ["TE"],
    "K": ["K"],
    "DL": ["DE", "DT", "DL"],
    "LB": ["LB"],
    "DB": ["S", "CB", "DB"],
    "DST": ["DST", "D/ST", "DEF"],
    "RB/WR/TE": ["RB", "WR", "TE"]
}

# Build alias lookup automatically from POSITION_MAP
POSITION_ALIASES = {}

for normalized_position, aliases in POSITION_MAP.items():
    if normalized_position == "RB/WR/TE":
        continue

    for alias in aliases:
        POSITION_ALIASES[alias.upper()] = normalized_position


def normalize_position(position):
    """
    Convert ESPN positions to optimizer positions.
    Example:
        DE -> DL
        DT -> DL
        CB -> DB
        S  -> DB
        D/ST -> DST
    """
    return POSITION_ALIASES.get(
        str(position).upper(),
        str(position).upper()
    )

def calculate_player_score(player, allow_average_fallback=True):

    if getattr(
        player,
        "projected_avg_points",
        0
    ) > 0:
        return player.projected_avg_points

    if getattr(
        player,
        "projected_points",
        0
    ) > 0:
        return player.projected_points

    if allow_average_fallback and getattr(player, "avg_points", 0) > 0:
        return player.avg_points

    return 0


def get_current_lineup_score(team_obj):

    return sum(
        calculate_player_score(player)
        for player in team_obj.roster
        if getattr(player, "lineupSlot", "BE") not in {"BE", "IR"}
    )


def get_optimal_lineup(
    team,
    lineup_requirements=None,
    allow_average_fallback=True,
):

    if lineup_requirements is None:
        lineup_requirements = {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "K": 1,
            "DST": 1,       # add if your league starts team defense
            "LB": 1,
            "DL": 1,
            "DB": 1,
            "RB/WR/TE": 1
        }

    players = []

    for player in team.roster:

        injury_status = str(
            getattr(player, "injuryStatus", "")
        ).upper()

        if injury_status in {"OUT", "IR", "SUSPENDED"}:
            continue

        players.append({
            "name": getattr(player, "name", "Unknown"),
            "position": normalize_position(
                getattr(player, "position", "")
            ),
            "score": calculate_player_score(
                player,
                allow_average_fallback=allow_average_fallback,
            ),
            "player_obj": player
        })

    position_groups = defaultdict(list)

    for player in players:
        position_groups[player["position"]].append(player)

    for position in position_groups:
        position_groups[position].sort(
            key=lambda x: x["score"],
            reverse=True
        )

    lineup = {}
    used_players = set()

    # Fill standard lineup slots
    fixed_positions = [
        "QB",
        "K",
        "DST",
        "LB",
        "DL",
        "DB"
    ]

    for position in fixed_positions:

               
        required_count = lineup_requirements.get(position, 0)

        candidates = position_groups.get(position, [])

        count = 0

        for player in candidates:

            player_id = getattr(
                player["player_obj"],
                "id",
                id(player["player_obj"])
            )

            if player_id in used_players:
                continue

            slot = (
                f"{position}{count + 1}"
                if required_count > 1
                else position
            )

            lineup[slot] = player
            used_players.add(player_id)

            count += 1

            if count >= required_count:
                break
        
        if count < required_count:
            print(
                f"Warning: only found {count} "
                f"{position} players, need {required_count}"
            )

    skill_players = []

    for player in players:

        player_id = getattr(
            player["player_obj"],
            "id",
            id(player["player_obj"])
        )

        if player_id in used_players:
            continue

        if player["position"] in {"RB", "WR", "TE"}:
            skill_players.append(player)


    skill_slots = (
        lineup_requirements["RB"]
        + lineup_requirements["WR"]
        + lineup_requirements["TE"]
        + lineup_requirements["RB/WR/TE"]
    )

    best_combo = None
    best_score = float("-inf")

    if len(skill_players) < skill_slots:
        return lineup, sum(
            player["score"]
            for player in lineup.values()
        )

    for combo in combinations(skill_players, skill_slots):

        rb_count = sum(
            1 for p in combo
            if p["position"] == "RB"
        )

        wr_count = sum(
            1 for p in combo
            if p["position"] == "WR"
        )

        te_count = sum(
            1 for p in combo
            if p["position"] == "TE"
        )

        if rb_count < lineup_requirements["RB"]:
            continue

        if wr_count < lineup_requirements["WR"]:
            continue

        if te_count < lineup_requirements["TE"]:
            continue

        score = sum(
            p["score"]
            for p in combo
        )

        if score > best_score:
            best_score = score
            best_combo = combo


    if best_combo:

        remaining = sorted(
            best_combo,
            key=lambda p: p["score"],
            reverse=True
        )
    
        rb_needed = lineup_requirements["RB"]

        for player in remaining[:]:
            if player["position"] == "RB" and rb_needed:

                slot = (
                    f"RB{lineup_requirements['RB'] - rb_needed + 1}"
                )

                lineup[slot] = player

                remaining.remove(player)

                rb_needed -= 1

        wr_needed = lineup_requirements["WR"]

        for player in remaining[:]:
            if player["position"] == "WR" and wr_needed:

                slot = (
                    f"WR{lineup_requirements['WR'] - wr_needed + 1}"
                )

                lineup[slot] = player

                remaining.remove(player)

                wr_needed -= 1
    
        te_needed = lineup_requirements["TE"]

        for player in remaining[:]:
            if player["position"] == "TE" and te_needed:

                lineup["TE"] = player

                remaining.remove(player)

                te_needed -= 1

        if remaining:
            lineup["RB/WR/TE"] = remaining[0]
    

    projected_total = sum(
        player["score"]
        for player in lineup.values()
    )

    return lineup, projected_total

import re

def lineup_to_dataframe(lineup):
    """
    Convert lineup dict to a list of dicts for DataFrame/table display.
    Removes trailing digits from slot names (e.g., 'RB1' -> 'RB').
    """
    DISPLAY_ORDER = [
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

    def slot_sort_key(slot):
        base = re.sub(r'\d+$', '', slot)
        try:
            return DISPLAY_ORDER.index(base)
        except ValueError:
            return 999

    rows = []
    for slot, player in sorted(lineup.items(), key=lambda x: slot_sort_key(x[0])):
        display_slot = re.sub(r'\d+$', '', slot) if slot not in {"RB/WR/TE"} else slot
        rows.append({
            "Slot": display_slot,
            "Player": player["name"],
            "Position": player["position"],
            "Score": round(player["score"], 2)
        })
    return rows
