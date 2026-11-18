import unittest

import pandas as pd

from services.trade_analysis import analyze_trade


class TradeAnalysisTests(unittest.TestCase):
    @staticmethod
    def _roster(players):
        return pd.DataFrame(
            players,
            columns=[
                "player_id",
                "player_name",
                "position",
                "projected_points",
            ],
        )

    def test_compares_projected_value_and_position_mix_for_both_teams(self):
        your_roster = self._roster([
            ("1", "Your RB", "RB", 15),
            ("2", "Your WR", "WR", 12),
        ])
        partner_roster = self._roster([
            ("3", "Their RB", "RB", 10),
            ("4", "Their TE", "TE", 8),
        ])

        result = analyze_trade(
            your_roster,
            partner_roster,
            ["1"],
            ["4"],
            {"RB": 2, "WR": 2, "TE": 1},
        )

        self.assertEqual(result["your_side"]["sent_projection"], 15)
        self.assertEqual(result["your_side"]["received_projection"], 8)
        self.assertEqual(result["your_side"]["net_projection"], -7)
        self.assertEqual(result["partner_side"]["net_projection"], 7)
        your_impact = result["your_side"]["position_impact"].set_index("Position")
        self.assertEqual(your_impact.loc["RB", "Change"], -1)
        self.assertEqual(your_impact.loc["TE", "Change"], 1)
        self.assertEqual(your_impact.loc["TE", "Fixed starting slots"], 1)

    def test_excludes_missing_projections_and_reports_the_count(self):
        your_roster = self._roster([("1", "Your Player", "WR", None)])
        partner_roster = self._roster([("2", "Their Player", "RB", 10)])

        result = analyze_trade(your_roster, partner_roster, ["1"], ["2"])

        self.assertEqual(result["your_side"]["received_projection"], 10)
        self.assertEqual(result["your_side"]["missing_projections"], 1)
        self.assertEqual(result["partner_side"]["missing_projections"], 1)

    def test_rejects_player_ids_not_present_on_the_roster(self):
        roster = self._roster([("1", "Player", "RB", 10)])

        with self.assertRaisesRegex(ValueError, "not on the roster"):
            analyze_trade(roster, roster, ["missing"], ["1"])

    def test_rejects_duplicate_roster_player_ids(self):
        roster = self._roster([
            ("1", "Player One", "RB", 10),
            ("1", "Player Two", "WR", 12),
        ])

        with self.assertRaisesRegex(ValueError, "duplicate player ID"):
            analyze_trade(roster, roster, ["1"], ["1"])

    def test_compares_optimized_lineups_before_and_after_the_trade(self):
        your_roster = self._roster([
            ("1", "Your RB 1", "RB", 20),
            ("2", "Your RB 2", "RB", 12),
            ("3", "Your WR", "WR", 8),
        ])
        partner_roster = self._roster([
            ("4", "Partner RB", "RB", 10),
            ("5", "Partner WR", "WR", 18),
        ])
        requirements = {
            "QB": 0,
            "RB": 1,
            "WR": 1,
            "TE": 0,
            "K": 0,
            "DST": 0,
            "DL": 0,
            "LB": 0,
            "DB": 0,
            "RB/WR/TE": 0,
        }

        result = analyze_trade(
            your_roster,
            partner_roster,
            ["1"],
            ["5"],
            lineup_requirements=requirements,
        )

        impact = result["your_side"]["lineup_impact"]
        self.assertEqual(impact["before_projection"], 28)
        self.assertEqual(impact["after_projection"], 30)
        self.assertEqual(impact["change"], 2)
        self.assertEqual(
            set(impact["after_lineup"]["Player"]),
            {"Your RB 2", "Partner WR"},
        )


if __name__ == "__main__":
    unittest.main()
