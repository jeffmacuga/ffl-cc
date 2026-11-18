import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services import access_control


class SiteAccessControlTests(unittest.TestCase):
    def test_reads_and_normalizes_cbs_team_mapping_from_secrets(self):
        secrets = {
            "access": {
                "team_by_email": {
                    " Member@Example.com ": " 12345 ",
                    "other@example.com": 67890,
                },
            }
        }
        with patch.object(access_control.st, "secrets", secrets):
            self.assertEqual(
                access_control.get_cbs_team_mapping(),
                {
                    "member@example.com": "12345",
                    "other@example.com": "67890",
                },
            )

    def test_rejects_non_numeric_cbs_team_ids(self):
        secrets = {
            "access": {
                "team_by_email": {"member@example.com": "team-123"},
            }
        }
        with patch.object(access_control.st, "secrets", secrets):
            with self.assertRaisesRegex(ValueError, "positive number"):
                access_control.get_cbs_team_mapping()

    def test_rejects_zero_cbs_team_id(self):
        secrets = {
            "access": {
                "team_by_email": {"member@example.com": "0"},
            }
        }
        with patch.object(access_control.st, "secrets", secrets):
            with self.assertRaisesRegex(ValueError, "positive number"):
                access_control.get_cbs_team_mapping()

    def test_missing_team_mapping_fails_closed(self):
        with patch.object(access_control.st, "secrets", {}), patch.object(
            access_control.st,
            "error",
        ) as show_error:
            self.assertFalse(access_control.require_site_access())

        show_error.assert_called_once()
        self.assertIn("not configured", show_error.call_args.args[0])

    def test_unauthenticated_user_is_prompted_to_sign_in(self):
        with (
            patch.object(
                access_control.st,
                "secrets",
                {"access": {"team_by_email": {"member@example.com": "12345"}}},
            ),
            patch.object(
                access_control.st,
                "user",
                SimpleNamespace(is_logged_in=False),
            ),
            patch.object(access_control.st, "title") as show_title,
            patch.object(access_control.st, "button") as show_button,
        ):
            self.assertFalse(access_control.require_site_access())

        show_title.assert_called_once_with("CBS League Sign In")
        show_button.assert_called_once_with(
            "Continue with Google",
            on_click=access_control.st.login,
        )

    def test_approved_verified_user_is_granted_access(self):
        user = SimpleNamespace(
            is_logged_in=True,
            email="Member@Example.com",
            email_verified=True,
        )
        with (
            patch.object(access_control.st, "secrets", {
                "access": {"team_by_email": {"member@example.com": "12345"}}
            }),
            patch.object(access_control.st, "user", user),
            patch.object(access_control.st.sidebar, "button") as show_logout,
        ):
            self.assertTrue(access_control.require_site_access())

        show_logout.assert_called_once_with(
            "Sign out",
            on_click=access_control.st.logout,
        )

    def test_unverified_user_is_denied_even_when_email_is_allowlisted(self):
        user = SimpleNamespace(
            is_logged_in=True,
            email="member@example.com",
            email_verified=False,
        )
        with (
            patch.object(access_control.st, "secrets", {
                "access": {"team_by_email": {"member@example.com": "12345"}}
            }),
            patch.object(access_control.st, "user", user),
            patch.object(access_control.st, "error") as show_error,
            patch.object(access_control.st.sidebar, "button"),
        ):
            self.assertFalse(access_control.require_site_access())

        self.assertIn("verified email", show_error.call_args.args[0])

    def test_user_not_on_allowlist_is_denied(self):
        user = SimpleNamespace(
            is_logged_in=True,
            email="outsider@example.com",
            email_verified=True,
        )
        with (
            patch.object(access_control.st, "secrets", {
                "access": {"team_by_email": {"member@example.com": "12345"}}
            }),
            patch.object(access_control.st, "user", user),
            patch.object(access_control.st, "error") as show_error,
            patch.object(access_control.st.sidebar, "button"),
        ):
            self.assertFalse(access_control.require_site_access())

        self.assertIn("not assigned to a CBS team", show_error.call_args.args[0])

    def test_returns_authenticated_members_team_id(self):
        user = SimpleNamespace(
            is_logged_in=True,
            email="Member@Example.com",
            email_verified=True,
        )
        with (
            patch.object(access_control.st, "secrets", {
                "access": {"team_by_email": {"member@example.com": "12345"}}
            }),
            patch.object(access_control.st, "user", user),
        ):
            self.assertEqual(
                access_control.get_authenticated_cbs_team_id(),
                "12345",
            )

    def test_unverified_user_has_no_team_assignment(self):
        user = SimpleNamespace(
            is_logged_in=True,
            email="member@example.com",
            email_verified=False,
        )
        with patch.object(access_control.st, "user", user):
            self.assertIsNone(access_control.get_authenticated_cbs_team_id())


if __name__ == "__main__":
    unittest.main()
