import unittest

from services.cbs_matchups import build_cbs_matchups


class CBSMatchupTests(unittest.TestCase):
    def test_combines_each_team_schedule_and_orients_scores_by_team(self):
        teams = {"1": "Away Team", "2": "Home Team"}
        schedules = [
            {
                "team_id": "2",
                "rows": [
                    {
                        "week": "1",
                        "opponent_id": "1",
                        "opponent": "Away Team",
                        "result": "Lost 87.0 - 117.0",
                    }
                ],
            },
            {
                "team_id": "1",
                "rows": [
                    {
                        "week": "1",
                        "opponent_id": "2",
                        "opponent": "Home Team",
                        "result": "Won 117.0 - 87.0",
                    }
                ],
            },
        ]

        matchups = build_cbs_matchups(teams, schedules)

        self.assertEqual(len(matchups), 1)
        self.assertEqual(matchups[0], {
            "Week": 1,
            "Team A": "Away Team",
            "Team B": "Home Team",
            "Team A Score": 117.0,
            "Team B Score": 87.0,
        })

    def test_preserves_future_games_and_bye_weeks(self):
        matchups = build_cbs_matchups(
            {"1": "Team One"},
            [
                {
                    "team_id": "1",
                    "rows": [
                        {
                            "week": "2",
                            "opponent_id": None,
                            "opponent": "BYE",
                            "result": "",
                        },
                        {
                            "week": "3",
                            "opponent_id": "2",
                            "opponent": "Team Two",
                            "result": "Scheduled",
                        },
                    ],
                }
            ],
        )

        self.assertEqual(matchups[0]["Team B"], "BYE")
        self.assertIsNone(matchups[0]["Team A Score"])
        self.assertEqual(matchups[1]["Team B"], "Team Two")
        self.assertIsNone(matchups[1]["Team B Score"])


if __name__ == "__main__":
    unittest.main()
