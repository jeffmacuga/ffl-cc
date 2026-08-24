# tests/test_roster_analysis.py

import pandas as pd
from services.roster_analysis import analyze_roster_needs


def test_roster_needs():

    roster = pd.DataFrame([
        {"position": "QB"},
        {"position": "RB"},
        {"position": "WR"},
    ])

    requirements = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
    }

    result = analyze_roster_needs(
        roster,
        requirements
    )

    assert result["QB"] == 0
    assert result["RB"] == 1
    assert result["WR"] == 1
    assert result["TE"] == 1
