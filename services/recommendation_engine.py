import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.roster_analysis import (
    analyze_roster_needs,
    calculate_need_weights,
    calculate_scarcity_bonus,
)


import pandas as pd

def recommend_players(
    available_players,
    my_roster,
    roster_requirements,
):
    needs = analyze_roster_needs(
        my_roster,
        roster_requirements
    )

    need_weights = calculate_need_weights(needs)

    scarcity_bonus = calculate_scarcity_bonus(
        available_players
    )

    recommendations = []

    for _, player in available_players.iterrows():

        position = player["position"]

        value_score = max(
            0,
            150 - player["ranking"]
        )

        need_bonus = need_weights.get(
            position,
            0
        )

        scarcity = scarcity_bonus.get(
            position,
            0
        )

        final_score = (
            value_score
            + need_bonus
            + scarcity
        )

        rec = {
            "player_id": None,
            "player_name": player["player_name"],
            "position": position,
            "rank": player["ranking"],
            "score": round(final_score, 2),
            "need_bonus": need_bonus,
            "scarcity": scarcity,
            "exposure": 0
        }

        rec["reason"] = build_reason(rec)

        recommendations.append(rec)

    recommendations_df = pd.DataFrame(recommendations)

    recommendations_df = recommendations_df.sort_values(
        "score",
        ascending=False
    )

    return recommendations_df


def build_reason(rec):
    reasons = []

    if rec["need_bonus"] >= 20:
        reasons.append("fills major roster need")

    if rec["scarcity"] >= 10:
        reasons.append("position becoming scarce")

    if rec["rank"] <= 25:
        reasons.append("elite value")

    if not reasons:
        reasons.append("best player available")

    return ", ".join(reasons)
