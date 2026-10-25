import os
import unittest
from unittest.mock import patch

from services.cbs_lineup_automation import run_cbs_lineup_refresh
from services.cbs_lineup_submission import CBSLineupError


ROSTER = {
    "team_id": "6",
    "team_name": "My CBS Team",
    "week": "7",
    "fingerprint": "fingerprint",
    "players": [{"provider_player_id": "101"}],
}
RESULT = {
    "complete": True,
    "missing_slots": [],
    "moves": [{
        "player_id": "101",
        "player": "Player One",
        "suggested_assignment": "QB",
        "suggested_roster_position": "QB",
    }],
}


class CBSLineupAutomationTests(unittest.TestCase):
    def setUp(self):
        self.roster_patcher = patch(
            "services.cbs_lineup_automation.fetch_my_cbs_roster",
            return_value=ROSTER,
        )
        self.optimizer_patcher = patch(
            "services.cbs_lineup_automation.optimize_cbs_lineup",
            return_value=RESULT,
        )
        self.apply_patcher = patch(
            "services.cbs_lineup_automation.apply_confirmed_lineup",
        )
        self.roster_patcher.start()
        self.optimizer_patcher.start()
        self.apply_lineup = self.apply_patcher.start()
        self.addCleanup(self.roster_patcher.stop)
        self.addCleanup(self.optimizer_patcher.stop)
        self.addCleanup(self.apply_patcher.stop)

    def test_scheduled_run_is_dry_run_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            outcome = run_cbs_lineup_refresh()

        self.assertEqual(outcome, "dry-run")
        self.apply_lineup.assert_not_called()

    def test_scheduled_run_submits_only_when_explicitly_enabled(self):
        with patch.dict(os.environ, {"CBS_AUTO_SUBMIT": "true"}, clear=True):
            outcome = run_cbs_lineup_refresh()

        self.assertEqual(outcome, "submitted")
        self.apply_lineup.assert_called_once_with(
            expected_fingerprint="fingerprint",
            team_id="6",
            week="7",
            moves=RESULT["moves"],
        )

    def test_manual_submission_requires_explicit_flag(self):
        outcome = run_cbs_lineup_refresh(manual=True)

        self.assertEqual(outcome, "dry-run")
        self.apply_lineup.assert_not_called()

    def test_manual_submit_works_without_scheduled_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            outcome = run_cbs_lineup_refresh(
                manual=True,
                manual_submit=True,
            )

        self.assertEqual(outcome, "submitted")
        self.apply_lineup.assert_called_once()

    def test_rejects_submission_flag_outside_manual_mode(self):
        with self.assertRaisesRegex(CBSLineupError, "manual mode"):
            run_cbs_lineup_refresh(manual_submit=True)

        self.apply_lineup.assert_not_called()

    def test_incomplete_lineup_fails_closed(self):
        with patch(
            "services.cbs_lineup_automation.optimize_cbs_lineup",
            return_value={
                "complete": False,
                "missing_slots": ["DST"],
                "moves": [],
            },
        ):
            with self.assertRaisesRegex(CBSLineupError, "DST"):
                run_cbs_lineup_refresh()

        self.apply_lineup.assert_not_called()

    def test_unchanged_lineup_skips_submission(self):
        with patch(
            "services.cbs_lineup_automation.optimize_cbs_lineup",
            return_value={
                "complete": True,
                "missing_slots": [],
                "moves": [],
            },
        ), patch.dict(os.environ, {"CBS_AUTO_SUBMIT": "true"}, clear=True):
            outcome = run_cbs_lineup_refresh()

        self.assertEqual(outcome, "unchanged")
        self.apply_lineup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
