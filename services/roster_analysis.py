from collections import Counter


def analyze_roster_needs(current_roster, roster_requirements):
    """
    current_roster = dataframe of your drafted players
    roster_requirements = dict

    Example:
    {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "FLEX": 1
    }
    """

    counts = Counter(current_roster["position"])

    needs = {}

    for position, required in roster_requirements.items():

        if position == "FLEX":
            continue

        current = counts.get(position, 0)

        needs[position] = max(required - current, 0)

    return needs

def calculate_need_weights(needs):
    """
    Converts needs into recommendation bonuses
    """

    weights = {}

    max_need = max(needs.values()) if needs else 1

    for pos, need in needs.items():

        if max_need == 0:
            weights[pos] = 0
        else:
            weights[pos] = round((need / max_need) * 25)

    return weights

def calculate_scarcity_bonus(
    available_players,
    top_n=20
):
    """
    Returns positional scarcity bonuses.
    """

    bonuses = {}

    for position in ["QB", "RB", "WR", "TE"]:

        pos_players = available_players[
            available_players["position"] == position
        ]

        remaining = len(pos_players)

        if remaining < 5:
            bonuses[position] = 20

        elif remaining < 10:
            bonuses[position] = 10

        else:
            bonuses[position] = 0

    return bonuses

def calculate_value_score(rank):
    """
    Lower rank = better score
    """

    return max(0, 150 - rank)

def exposure_penalty(exposure_pct):

    if exposure_pct >= 75:
        return 20

    if exposure_pct >= 50:
        return 10

    if exposure_pct >= 30:
        return 5

    return 0