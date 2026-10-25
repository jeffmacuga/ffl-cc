import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
)
from services.cbs_lineup_submission import (
    CBSLineupError,
    _fetch_live_team,
    _is_locked,
    is_player_unlocked,
    _launch_browser,
    _merge_page_projections,
    _open_cbs_teams_page,
    _roster_fingerprint,
    _verify_assignments,
    build_lineup_payload,
)


class CBSLineupSubmissionTests(unittest.TestCase):
    def test_launches_bundled_chromium_headless(self):
        class FakeChromium:
            executable_path = __file__

            def launch(self, **options):
                self.options = options
                return "browser"

        playwright = SimpleNamespace(chromium=FakeChromium())

        browser = _launch_browser(playwright)

        self.assertEqual(browser, "browser")
        self.assertEqual(
            playwright.chromium.options,
            {"headless": True, "args": ["--disable-popup-blocking"]},
        )

    def test_installs_missing_playwright_browser_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "chromium"

            def install_browser(*args, **kwargs):
                executable.touch()

            chromium = SimpleNamespace(
                executable_path=str(executable),
                launch=lambda **options: "browser",
            )
            playwright = SimpleNamespace(chromium=chromium)
            with patch(
                "services.cbs_lineup_submission.subprocess.run",
                side_effect=install_browser,
            ) as run:
                browser = _launch_browser(playwright)

        self.assertEqual(browser, "browser")
        run.assert_called_once()

    def test_reports_browser_launch_dependency_failure(self):
        class FakeChromium:
            executable_path = __file__

            def launch(self, **options):
                raise PlaywrightError("shared library missing")

        with self.assertRaisesRegex(
            CBSLineupError,
            "Linux libraries listed in the root `packages.txt`",
        ) as raised:
            _launch_browser(SimpleNamespace(chromium=FakeChromium()))

        self.assertIsInstance(raised.exception.__cause__, PlaywrightError)

    def test_opens_league_home_then_team_page_and_captures_fresh_token(self):
        class FakeContext:
            @contextmanager
            def expect_event(self, event, predicate, timeout):
                self.event = event
                self.predicate = predicate
                self.timeout = timeout
                self.request = None
                yield self
                if self.request is None:
                    raise PlaywrightTimeoutError("No matching request")

            @property
            def value(self):
                return self.request

        class FakePage:
            def __init__(self):
                self.context = FakeContext()
                self.page_urls = []

            def goto(self, url, **kwargs):
                self.page_urls.append(url)
                request = SimpleNamespace(
                    url=(
                        "https://kjfha.football.cbssports.com/api/league/feed"
                        "?access_token=fresh-token"
                    )
                )
                if self.context.predicate(request):
                    self.context.request = request

        page = FakePage()

        token = _open_cbs_teams_page(page, "6")

        self.assertEqual(token, "fresh-token")
        self.assertEqual(page.context.event, "request")
        self.assertEqual(page.context.timeout, 120000)
        self.assertEqual(
            page.page_urls,
            [
                "https://kjfha.football.cbssports.com",
                "https://kjfha.football.cbssports.com/teams/6",
            ],
        )

    def test_reports_when_cbs_never_issues_authorization_request(self):
        class FakeContext:
            @contextmanager
            def expect_event(self, event, predicate, timeout):
                yield self
                raise PlaywrightTimeoutError("No matching request")

        class FakePage:
            def __init__(self):
                self.context = FakeContext()

            def goto(self, url, **kwargs):
                self.page_url = url

        with self.assertRaisesRegex(CBSLineupError, "resolve any CAPTCHA"):
            _open_cbs_teams_page(FakePage())

    def test_team_specific_roster_read_checks_requested_team_id(self):
        class FakePage:
            def __init__(self):
                self.roster_url = None

            def evaluate(self, script, argument=None):
                if argument is None:
                    return {"101": "11.34"}
                self.roster_url = argument
                return {
                    "status": 200,
                    "text": json.dumps({
                        "body": {
                            "rosters": {
                                "period": 7,
                                "teams": [{
                                    "id": "6",
                                    "name": "Kalifornication",
                                    "players": [{
                                        "id": "101",
                                        "projected_points": "0.0",
                                    }],
                                }],
                            }
                        }
                    }),
                }

        page = FakePage()
        team, week = _fetch_live_team(
            page,
            "6",
            access_token="fresh-token",
        )

        self.assertEqual((team["id"], week), ("6", "7"))
        self.assertEqual(team["players"][0]["projected_points"], 11.34)
        self.assertIn("team_id=6", page.roster_url)
        self.assertIn("access_token=fresh-token", page.roster_url)
        with self.assertRaises(CBSLineupError):
            _fetch_live_team(
                FakePage(),
                "8",
                access_token="fresh-token",
            )

    def test_merges_displayed_projections_by_cbs_player_id(self):
        team = {
            "players": [
                {"id": "101", "projected_points": "0.0"},
                {"id": "202", "projected_points": "0.0"},
            ]
        }

        _merge_page_projections(team, {"101": "11.34", "202": "17.81"})

        self.assertEqual(
            [player["projected_points"] for player in team["players"]],
            [11.34, 17.81],
        )

    def test_blank_displayed_projection_is_marked_missing(self):
        team = {"players": [{"id": "101", "projected_points": "0.0"}]}

        _merge_page_projections(team, {"101": ""})

        self.assertIsNone(team["players"][0]["projected_points"])

    def test_rejects_unmatched_roster_player_projection(self):
        team = {"players": [{"id": "101", "projected_points": "0.0"}]}

        with self.assertRaises(CBSLineupError):
            _merge_page_projections(team, {})

    def test_rejects_unrecognized_displayed_projection(self):
        team = {"players": [{"id": "101", "projected_points": "0.0"}]}

        with self.assertRaises(CBSLineupError):
            _merge_page_projections(team, {"101": "not available"})

    def test_builds_partial_active_and_reserve_payload(self):
        payload = build_lineup_payload(
            "8",
            "7",
            [
                {
                    "player_id": "101",
                    "suggested_assignment": "QB",
                    "suggested_roster_position": "QB",
                },
                {
                    "player_id": "202",
                    "suggested_assignment": "Bench",
                    "suggested_roster_position": "WR-TE",
                },
            ],
        )

        self.assertEqual(payload, {
            "team": "8",
            "active": {"101": {"pos": "QB"}},
            "reserve": {"202": {"pos": "WR-TE"}},
            "point": "7",
        })

    def test_builds_payload_without_empty_assignment_groups(self):
        payload = build_lineup_payload(
            "8",
            "7",
            [{
                "player_id": "101",
                "suggested_assignment": "RB",
                "suggested_roster_position": "RB",
            }],
        )

        self.assertEqual(payload, {
            "team": "8",
            "active": {"101": {"pos": "RB"}},
            "point": "7",
        })

    def test_roster_fingerprint_changes_when_team_week_or_assignment_changes(self):
        team = {
            "id": "8",
            "players": [
                {
                    "id": "101",
                    "fullname": "Quarterback",
                    "position": "QB",
                    "eligible_positions_display": "QB",
                    "projected_points": "10",
                    "roster_status": "A",
                    "roster_pos": "QB",
                    "is_locked": "0",
                }
            ],
        }
        original = _roster_fingerprint(team, "7")
        changed = {
            **team,
            "players": [
                {
                    **team["players"][0],
                    "roster_status": "RS",
                }
            ],
        }
        changed_projection = {
            **team,
            "players": [{
                **team["players"][0],
                "projected_points": "12",
            }],
        }

        self.assertNotEqual(original, _roster_fingerprint(changed, "7"))
        self.assertNotEqual(original, _roster_fingerprint(team, "8"))
        self.assertNotEqual(original, _roster_fingerprint({**team, "id": "9"}, "7"))
        self.assertNotEqual(
            original,
            _roster_fingerprint(changed_projection, "7"),
        )

    def test_verifies_active_and_reserve_assignments(self):
        team = {
            "players": [
                {"id": "101", "roster_status": "A", "roster_pos": "QB"},
                {"id": "202", "roster_status": "RS", "roster_pos": "WR-TE"},
            ]
        }
        moves = [
            {
                "player_id": "101",
                "player": "Quarterback",
                "suggested_assignment": "QB",
                "suggested_roster_position": "QB",
            },
            {
                "player_id": "202",
                "player": "Receiver",
                "suggested_assignment": "Bench",
                "suggested_roster_position": "WR-TE",
            },
        ]

        _verify_assignments(team, moves)

    def test_verification_rejects_unapplied_move(self):
        team = {
            "players": [
                {"id": "101", "roster_status": "RS", "roster_pos": "QB"}
            ]
        }
        moves = [{
            "player_id": "101",
            "player": "Quarterback",
            "suggested_assignment": "QB",
            "suggested_roster_position": "QB",
        }]

        with self.assertRaises(CBSLineupError):
            _verify_assignments(team, moves)

    def test_lock_status_parsing(self):
        self.assertTrue(_is_locked("1"))
        self.assertTrue(_is_locked(True))
        self.assertFalse(_is_locked("0"))
        self.assertFalse(_is_locked(None))
        self.assertTrue(is_player_unlocked("0"))
        self.assertTrue(is_player_unlocked(False))
        self.assertFalse(is_player_unlocked(None))
        self.assertFalse(is_player_unlocked("unknown"))


if __name__ == "__main__":
    unittest.main()
