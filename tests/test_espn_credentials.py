import unittest
from unittest.mock import patch

from pages import standings


class ESPNLeagueCredentialsTests(unittest.TestCase):
    def test_missing_credentials_stop_before_espn_request(self):
        selected_league = {
            "league_id": 123,
            "year": 2026,
            "swid": "",
            "espn_s2": "",
        }

        with (
            patch.object(standings.st, "error") as show_error,
            patch.object(standings.st, "stop", side_effect=RuntimeError("stop")),
            patch.object(standings, "League") as espn_league,
        ):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                standings.load_espn_league(selected_league)

        show_error.assert_called_once()
        self.assertIn("ESPN_SWID", show_error.call_args.args[0])
        self.assertIn("ESPN_S2", show_error.call_args.args[0])
        espn_league.assert_not_called()


if __name__ == "__main__":
    unittest.main()
