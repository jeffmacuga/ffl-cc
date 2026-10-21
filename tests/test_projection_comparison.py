import unittest
from types import SimpleNamespace

import pandas as pd

from services.projection_comparison import (
    add_projection_columns,
    append_projection_totals,
    build_cbs_projection_lookup,
    build_espn_optimized_projection_lookup,
)


class ProjectionComparisonTests(unittest.TestCase):
    def test_builds_espn_lookup_using_projection_fields(self):
        league = SimpleNamespace(
            teams=[
                SimpleNamespace(
                    roster=[
                        SimpleNamespace(
                            name="Player One",
                            projected_avg_points=12.5,
                            projected_points=120,
                            avg_points=10,
                        )
                    ]
                )
            ]
        )

        lookup = build_espn_optimized_projection_lookup(league)

        self.assertEqual(
            lookup["playerone"],
            {"projection": 12.5, "average_points": None},
        )

    def test_adds_each_league_projection_and_the_available_mean(self):
        lineup = pd.DataFrame(
            [
                {"Player": "A.J. Brown", "Position": "WR"},
                {"Player": "Unmatched Player", "Position": "QB"},
            ]
        )
        cbs_lookup = build_cbs_projection_lookup(
            [
                {
                    "player_name": "AJ Brown",
                    "projected_points": 13.0,
                }
            ]
        )

        result = add_projection_columns(
            lineup,
            {
                "KickButt Optimized Projection": {
                    "ajbrown": {"projection": 11.0}
                },
                "AFS Optimized Projection": {
                    "ajbrown": {"projection": 15.0}
                },
                "CBS Optimized Projection": cbs_lookup,
            },
        )

        self.assertEqual(result.loc[0, "KickButt Optimized Projection"], 11.0)
        self.assertEqual(result.loc[0, "AFS Optimized Projection"], 15.0)
        self.assertEqual(result.loc[0, "CBS Optimized Projection"], 13.0)
        self.assertEqual(result.loc[0, "Aggregate Projection"], 13.0)
        self.assertTrue(pd.isna(result.loc[1, "Aggregate Projection"]))
        self.assertTrue(pd.isna(result.loc[1, "AFS Optimized Projection"]))

    def test_aggregate_uses_available_projections_only(self):
        lineup = pd.DataFrame([{"Player": "Player One"}])

        result = add_projection_columns(
            lineup,
            {
                "KickButt Optimized Projection": {
                    "playerone": {"projection": 10.0}
                },
                "AFS Optimized Projection": {},
                "CBS Optimized Projection": {
                    "playerone": {"projection": 14.0}
                },
            },
        )

        self.assertEqual(result.loc[0, "Aggregate Projection"], 12.0)

    def test_appends_projection_totals_below_lineup(self):
        lineup = pd.DataFrame(
            [
                {
                    "Slot": "QB",
                    "Player": "Player One",
                    "ESPN Projection": 12.5,
                    "CBS Projection": 10.0,
                },
                {
                    "Slot": "RB",
                    "Player": "Player Two",
                    "ESPN Projection": None,
                    "CBS Projection": 8.0,
                },
            ]
        )

        result = append_projection_totals(
            lineup,
            ["ESPN Projection", "CBS Projection"],
        )

        self.assertEqual(result.loc[2, "Player"], "Total")
        self.assertEqual(result.loc[2, "ESPN Projection"], 12.5)
        self.assertEqual(result.loc[2, "CBS Projection"], 18.0)
        self.assertEqual(result.loc[2, "Slot"], "")

    def test_all_missing_projection_total_remains_blank(self):
        lineup = pd.DataFrame(
            [{"Player": "Player One", "CBS Projection": None}]
        )

        result = append_projection_totals(lineup, ["CBS Projection"])

        self.assertTrue(pd.isna(result.loc[1, "CBS Projection"]))


    def test_ambiguous_names_are_not_matched(self):
        lookup = build_cbs_projection_lookup(
            [
                {
                    "player_name": "Player A",
                    "projected_points": 10,
                    "average_points": 8,
                },
                {
                    "player_name": "Player-A",
                    "projected_points": 12,
                    "average_points": 9,
                },
            ]
        )

        self.assertNotIn("playera", lookup)


if __name__ == "__main__":
    unittest.main()
