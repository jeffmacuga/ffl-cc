from data.repositories.players_repo import get_available_players
from data.repositories.roster_repo import get_my_roster
from data.repositories.roster_requirements_repo import (
    get_roster_requirements
)

from services.recommendation_engine import (
    analyze_roster_needs,
    recommend_players
)


def get_recommendations():

    roster_df = get_my_roster()
    available_df = get_available_players()
    requirements_df = get_roster_requirements()

    print("\nMY ROSTER")
    print(roster_df)
    
    requirements_dict = dict(
        zip(
            requirements_df["position"],
            requirements_df["required_count"]
        )
    )

    roster_needs = analyze_roster_needs(
        roster_df,
        requirements_dict
    )

    recommendations = recommend_players(
        available_players=available_df,
        my_roster=roster_df,
        roster_requirements=requirements_dict
    )

    return {
        "recommendations": recommendations,
        "roster_needs": roster_needs,
        "available_players": available_df
    }


def filter_by_position(df, position):

    if position == "ALL":
        return df

    return df[df["position"] == position]