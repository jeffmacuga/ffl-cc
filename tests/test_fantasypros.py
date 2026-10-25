import json
import unittest
from unittest.mock import patch

from services.fantasypros import (
    FantasyProsAPIError,
    fetch_weekly_projections,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FantasyProsProjectionTests(unittest.TestCase):
    def setUp(self):
        self.roster = [
            {
                "provider_player_id": "101",
                "player_name": "Christian McCaffrey",
                "position": "RB",
                "pro_team": "SF",
                "projected_points": 21.0,
            },
            {
                "provider_player_id": "102",
                "player_name": "Unlisted Player",
                "position": "RB",
                "projected_points": 4.0,
            },
        ]

    @patch("services.fantasypros.urlopen")
    def test_fetches_ppr_projection_and_preserves_cbs_projection(self, urlopen):
        urlopen.return_value = FakeResponse({
            "season": "2026",
            "week": "7",
            "positions": "RB",
            "players": [
                {
                    "fpid": 123,
                    "name": "Christian McCaffrey",
                    "position_id": "RB",
                    "team_id": "SF",
                    "stats": {
                        "points": 17.78,
                        "points_ppr": 23.3,
                        "points_half": 20.54,
                    },
                },
            ],
        })

        result = fetch_weekly_projections(
            self.roster,
            season=2026,
            week=7,
            scoring="PPR",
            api_key="test-key",
        )

        self.assertEqual(
            result["roster"][0]["fantasypros_projected_points"],
            23.3,
        )
        self.assertEqual(result["roster"][0]["projected_points"], 23.3)
        self.assertEqual(result["roster"][0]["cbs_projected_points"], 21.0)
        self.assertEqual(result["missing_players"], ["Unlisted Player"])
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://api.fantasypros.com/public/v2/json/nfl/2026/"
            "projections?position=RB&week=7",
        )
        self.assertEqual(request.get_header("X-api-key"), "test-key")

    @patch("services.fantasypros.urlopen")
    def test_selects_standard_projection_when_requested(self, urlopen):
        urlopen.return_value = FakeResponse({
            "players": [
                {
                    "name": "Christian McCaffrey",
                    "team_id": "SF",
                    "stats": {
                        "points": 17.78,
                        "points_ppr": 23.3,
                        "points_half": 20.54,
                    },
                },
            ],
        })

        result = fetch_weekly_projections(
            self.roster[:1],
            season=2026,
            week=7,
            scoring="Standard",
            api_key="test-key",
        )

        self.assertEqual(
            result["roster"][0]["fantasypros_projected_points"],
            17.78,
        )

    def test_reports_missing_api_key(self):
        with self.assertRaisesRegex(FantasyProsAPIError, "FANTASYPROS_API_KEY"):
            fetch_weekly_projections(
                self.roster,
                season=2026,
                week=7,
                api_key="",
            )

    @patch("services.fantasypros.urlopen")
    def test_rejects_response_for_different_week(self, urlopen):
        urlopen.return_value = FakeResponse({
            "season": "2026",
            "week": "6",
            "players": [],
        })

        with self.assertRaisesRegex(FantasyProsAPIError, "not 7"):
            fetch_weekly_projections(
                self.roster,
                season=2026,
                week=7,
                api_key="test-key",
            )


if __name__ == "__main__":
    unittest.main()
