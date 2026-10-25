import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import services.espn_lineup_submission as submission
from services.espn_lineup_submission import (
    ESPNLineupSubmissionError,
    apply_confirmed_espn_lineup,
    build_espn_lineup_proposal,
)


LEAGUE_CONFIG = {
    "league_id": 123,
    "year": 2026,
    "swid": "{member-id}",
    "espn_s2": "test-cookie",
}
FINGERPRINT = ((1, 20), (2, 0))
EXPECTED_SLOTS = {1: 0, 2: 20}
CHANGES = [{
    "playerId": 1,
    "type": "LINEUP",
    "fromLineupSlotId": 20,
    "toLineupSlotId": 0,
}]


class ESPNLineupSubmissionTests(unittest.TestCase):
    def _submission_mocks(self, response=None, verify_side_effect=None):
        league = SimpleNamespace(nfl_week=7)
        team = SimpleNamespace(team_id=3)
        return (
            patch.object(submission, "League", return_value=league),
            patch.object(submission, "_owned_team", return_value=team),
            patch.object(
                submission,
                "_lineup_fingerprint",
                return_value=FINGERPRINT,
            ),
            patch.object(submission, "_load_schedule", return_value={}),
            patch.object(
                submission,
                "build_lineup_changes",
                return_value=(EXPECTED_SLOTS, CHANGES),
            ),
            patch.object(
                submission.requests,
                "post",
                return_value=response or Mock(),
            ),
            patch.object(
                submission,
                "_verify_lineup",
                side_effect=verify_side_effect,
            ),
        )

    def test_builds_proposal_from_live_schedule_and_roster(self):
        league = SimpleNamespace(year=2026)
        team = SimpleNamespace(team_id=3)

        with (
            patch.object(submission, "_load_schedule", return_value={}),
            patch.object(
                submission,
                "build_lineup_changes",
                return_value=(EXPECTED_SLOTS, CHANGES),
            ),
            patch.object(
                submission,
                "_lineup_fingerprint",
                return_value=FINGERPRINT,
            ),
        ):
            proposal = build_espn_lineup_proposal(league, team)

        self.assertEqual(proposal, {
            "team_id": 3,
            "fingerprint": FINGERPRINT,
            "expected_slots": EXPECTED_SLOTS,
            "changes": CHANGES,
        })

    def test_submits_only_after_fresh_roster_and_proposal_match(self):
        league = SimpleNamespace(nfl_week=7)
        team = SimpleNamespace(team_id=3)
        response = Mock()

        with (
            patch.object(submission, "League", return_value=league),
            patch.object(submission, "_owned_team", return_value=team),
            patch.object(
                submission,
                "_lineup_fingerprint",
                return_value=FINGERPRINT,
            ),
            patch.object(submission, "_load_schedule", return_value={}),
            patch.object(
                submission,
                "build_lineup_changes",
                return_value=(EXPECTED_SLOTS, CHANGES),
            ),
            patch.object(submission.requests, "post", return_value=response) as post,
            patch.object(submission, "_verify_lineup") as verify,
        ):
            apply_confirmed_espn_lineup(
                LEAGUE_CONFIG,
                3,
                FINGERPRINT,
                EXPECTED_SLOTS,
                CHANGES,
            )

        post.assert_called_once()
        response.raise_for_status.assert_called_once()
        verify.assert_called_once_with(
            LEAGUE_CONFIG,
            LEAGUE_CONFIG["swid"],
            EXPECTED_SLOTS,
        )

    def test_stale_roster_is_rejected_before_submission(self):
        league = SimpleNamespace(nfl_week=7)
        team = SimpleNamespace(team_id=3)

        with (
            patch.object(submission, "League", return_value=league),
            patch.object(submission, "_owned_team", return_value=team),
            patch.object(
                submission,
                "_lineup_fingerprint",
                return_value=((1, 20), (2, 2)),
            ),
            patch.object(submission.requests, "post") as post,
        ):
            with self.assertRaisesRegex(
                ESPNLineupSubmissionError,
                "roster changed",
            ):
                apply_confirmed_espn_lineup(
                    LEAGUE_CONFIG,
                    3,
                    FINGERPRINT,
                    EXPECTED_SLOTS,
                    CHANGES,
                )

        post.assert_not_called()

    def test_submission_http_error_reports_status_and_requires_roster_check(self):
        response = Mock(status_code=409)
        response.json.return_value = {
            "messages": ["Player is locked."],
        }
        error = submission.requests.HTTPError(response=response)
        patches = self._submission_mocks()
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patch.object(submission.requests, "post", side_effect=error),
        ):
            with self.assertRaisesRegex(
                ESPNLineupSubmissionError,
                r"HTTP 409.*ESPN detail: Player is locked.*"
                r"Check your ESPN roster before retrying",
            ) as raised:
                apply_confirmed_espn_lineup(
                    LEAGUE_CONFIG,
                    3,
                    FINGERPRINT,
                    EXPECTED_SLOTS,
                    CHANGES,
                )

        self.assertNotIn("cookies", str(raised.exception).lower())

    def test_verification_network_error_says_submission_may_have_succeeded(self):
        patches = self._submission_mocks(
            verify_side_effect=submission.requests.Timeout(
                "sensitive request details"
            )
        )
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
        ):
            with self.assertRaisesRegex(
                ESPNLineupSubmissionError,
                "ESPN received the lineup submission.*Check your ESPN roster",
            ) as raised:
                apply_confirmed_espn_lineup(
                    LEAGUE_CONFIG,
                    3,
                    FINGERPRINT,
                    EXPECTED_SLOTS,
                    CHANGES,
                )

        self.assertNotIn("sensitive request details", str(raised.exception))

    def test_submission_network_error_warns_against_blind_retry(self):
        patches = self._submission_mocks()
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patch.object(
                submission.requests,
                "post",
                side_effect=submission.requests.Timeout(
                    "sensitive request details"
                ),
            ),
        ):
            with self.assertRaisesRegex(
                ESPNLineupSubmissionError,
                "could not be confirmed.*may have accepted it",
            ) as raised:
                apply_confirmed_espn_lineup(
                    LEAGUE_CONFIG,
                    3,
                    FINGERPRINT,
                    EXPECTED_SLOTS,
                    CHANGES,
                )

        self.assertNotIn("sensitive request details", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
