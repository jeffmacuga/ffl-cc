import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.recommendation_engine import build_reason
from services.recommendation_engine import recommend_players


def test_build_reason_all_factors():
    rec = {
        "need_bonus": 25,
        "scarcity": 10,
        "rank": 10
    }

    result = build_reason(rec)

    assert "fills major roster need" in result
    assert "position becoming scarce" in result
    assert "elite value" in result


def test_build_reason_fallback():
    rec = {
        "need_bonus": 0,
        "scarcity": 0,
        "rank": 100
    }

    result = build_reason(rec)

    assert result == "best player available"
