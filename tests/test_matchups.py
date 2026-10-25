import unittest
from types import SimpleNamespace

from pages.matchups import build_matchup_player_rows, build_matchup_summary


class MatchupSummaryTests(unittest.TestCase):
    def test_builds_summary_with_team_names_scores_and_projections(self):
        away = SimpleNamespace(team_name="Away Team")
        home = SimpleNamespace(team_name="Home Team")
        box_score = SimpleNamespace(
            away_team=away,
            away_score=87.5,
            away_projected=112.2,
            home_team=home,
            home_score=101.0,
            home_projected=106.7,
        )

        summary = build_matchup_summary([box_score])

        self.assertEqual(summary.iloc[0].to_dict(), {
            "Away Team": "Away Team",
            "Away Score": 87.5,
            "Away Projected": 112.2,
            "Home Team": "Home Team",
            "Home Score": 101.0,
            "Home Projected": 106.7,
        })

    def test_supports_byes_and_empty_matchup_sets(self):
        box_score = SimpleNamespace(
            away_team=None,
            away_score=0,
            away_projected=0,
            home_team=SimpleNamespace(team_name="Home Team"),
            home_score=100,
            home_projected=105,
        )

        self.assertEqual(
            build_matchup_summary([box_score]).iloc[0]["Away Team"],
            "BYE",
        )
        self.assertEqual(len(build_matchup_summary([])), 0)

    def test_builds_player_rows_with_points_and_game_status(self):
        player = SimpleNamespace(
            slot_position="RB",
            name="Player One",
            proTeam="SEA",
            game_date="2026-10-25",
            game_played=100,
            points=18.4,
            projected_points=15.2,
        )
        box_score = SimpleNamespace(away_lineup=[player])

        rows = build_matchup_player_rows(box_score, "away")

        self.assertEqual(rows.iloc[0].to_dict(), {
            "Slot": "RB",
            "Player": "Player One",
            "NFL Team": "SEA",
            "Status": "Final",
            "Points": 18.4,
            "Projected Points": 15.2,
        })


if __name__ == "__main__":
    unittest.main()
