import unittest

from services.lineup_explanation import explain_lineup


class LineupExplanationTests(unittest.TestCase):
    def test_explains_projection_totals_and_suggested_changes(self):
        explanation = explain_lineup({
            "projection_source": "CBS",
            "optimizer_objective": "The optimizer maximizes CBS projections.",
            "projection_summary": {"current": 70, "optimized": 75},
            "suggested_changes": [
                {
                    "Player": "Player One",
                    "Position": "RB",
                    "Current Assignment": "Bench",
                    "Suggested Assignment": "FLEX",
                    "Projection": 12.25,
                },
            ],
        })

        self.assertIn("maximizes CBS projections", explanation)
        self.assertIn("projection source is CBS", explanation)
        self.assertIn("70.00 for the current lineup and 75.00", explanation)
        self.assertIn("Player One (RB): Bench -> FLEX; projection 12.25", explanation)
        self.assertIn("Projection accuracy", explanation)

    def test_calls_out_uncertainty_and_handles_missing_projection_totals(self):
        explanation = explain_lineup({
            "projection_source": "ESPN",
            "projection_summary": {"current": None, "optimized": 14},
            "suggested_changes": [],
            "uncertainties": ["One optimized player has no projection."],
        })

        self.assertNotIn("Available projections total", explanation)
        self.assertIn("no suggested assignment changes", explanation)
        self.assertIn("Uncertainty to review", explanation)
        self.assertIn("no projection", explanation)

    def test_does_not_invent_projection_or_change_reason(self):
        explanation = explain_lineup({
            "projection_source": "CBS",
            "suggested_changes": [
                {
                    "Player": "Player Two",
                    "Current Assignment": "RB",
                    "Suggested Assignment": "Bench",
                    "Projection": None,
                },
            ],
        })

        self.assertIn("Player Two: RB -> Bench", explanation)
        self.assertNotIn("projection None", explanation)
        self.assertNotIn("projected to score", explanation)


if __name__ == "__main__":
    unittest.main()
