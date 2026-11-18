import unittest
from unittest.mock import MagicMock, patch

from services import access_control


ACCESS_CODES = [
    {"code": "member-access-code-1234567890", "team_id": "12345"},
    {"code": "second-member-access-code-1234", "team_id": "67890"},
]


def mocked_form():
    form = MagicMock()
    form.__enter__.return_value = form
    form.__exit__.return_value = False
    return form


class CBSTeamAccessCodeTests(unittest.TestCase):
    def test_reads_team_access_codes_as_hashed_team_mapping(self):
        with patch.object(
            access_control.st,
            "secrets",
            {"access": {"team_access_codes": ACCESS_CODES}},
        ):
            mapping = access_control.get_cbs_code_mapping()

        self.assertEqual(
            mapping,
            {
                access_control._hash_code("member-access-code-1234567890"): "12345",
                access_control._hash_code("second-member-access-code-1234"): "67890",
            },
        )
        self.assertNotIn("member-access-code-1234567890", mapping)

    def test_rejects_short_access_codes(self):
        with patch.object(
            access_control.st,
            "secrets",
            {"access": {"team_access_codes": [{"code": "short", "team_id": "1"}]}},
        ):
            with self.assertRaisesRegex(ValueError, "at least 20"):
                access_control.get_cbs_code_mapping()

    def test_rejects_invalid_team_ids(self):
        with patch.object(
            access_control.st,
            "secrets",
            {
                "access": {
                    "team_access_codes": [
                        {"code": "member-access-code-1234567890", "team_id": "0"}
                    ]
                }
            },
        ):
            with self.assertRaisesRegex(ValueError, "positive numbers"):
                access_control.get_cbs_code_mapping()

    def test_missing_codes_fail_closed(self):
        with (
            patch.object(access_control.st, "secrets", {}),
            patch.object(access_control.st, "error") as show_error,
        ):
            self.assertFalse(access_control.require_site_access())

        show_error.assert_called_once()
        self.assertIn("not configured", show_error.call_args.args[0])

    def test_invalid_code_does_not_authenticate(self):
        session_state = {}
        form = mocked_form()
        with (
            patch.object(
                access_control.st,
                "secrets",
                {"access": {"team_access_codes": ACCESS_CODES}},
            ),
            patch.object(access_control.st, "session_state", session_state),
            patch.object(access_control.st, "title"),
            patch.object(access_control.st, "write"),
            patch.object(access_control.st, "form", return_value=form),
            patch.object(access_control.st, "text_input", return_value="invalid-code"),
            patch.object(access_control.st, "form_submit_button", return_value=True),
            patch.object(access_control.st, "error") as show_error,
        ):
            self.assertFalse(access_control.require_site_access())

        self.assertNotIn(access_control.SESSION_CODE_HASH_KEY, session_state)
        show_error.assert_called_once_with("That access code is not valid.")

    def test_valid_code_authenticates_and_stores_only_its_hash(self):
        session_state = {}
        form = mocked_form()
        with (
            patch.object(
                access_control.st,
                "secrets",
                {"access": {"team_access_codes": ACCESS_CODES}},
            ),
            patch.object(access_control.st, "session_state", session_state),
            patch.object(access_control.st, "title"),
            patch.object(access_control.st, "write"),
            patch.object(access_control.st, "form", return_value=form),
            patch.object(
                access_control.st,
                "text_input",
                return_value="member-access-code-1234567890",
            ),
            patch.object(access_control.st, "form_submit_button", return_value=True),
            patch.object(access_control.st, "rerun"),
        ):
            self.assertFalse(access_control.require_site_access())

        self.assertEqual(
            session_state[access_control.SESSION_CODE_HASH_KEY],
            access_control._hash_code("member-access-code-1234567890"),
        )

    def test_authenticated_session_is_bound_to_its_configured_team(self):
        session_state = {
            access_control.SESSION_CODE_HASH_KEY: access_control._hash_code(
                "member-access-code-1234567890"
            )
        }
        with (
            patch.object(
                access_control.st,
                "secrets",
                {"access": {"team_access_codes": ACCESS_CODES}},
            ),
            patch.object(access_control.st, "session_state", session_state),
            patch.object(access_control.st.sidebar, "button") as show_logout,
        ):
            self.assertTrue(access_control.require_site_access())
            self.assertEqual(access_control.get_authenticated_cbs_team_id(), "12345")

        show_logout.assert_called_once_with(
            "Sign out",
            on_click=access_control._sign_out,
        )

    def test_removed_code_revokes_existing_session(self):
        session_state = {
            access_control.SESSION_CODE_HASH_KEY: access_control._hash_code(
                "member-access-code-1234567890"
            )
        }
        form = mocked_form()
        with (
            patch.object(
                access_control.st,
                "secrets",
                {"access": {"team_access_codes": ACCESS_CODES[1:]}},
            ),
            patch.object(access_control.st, "session_state", session_state),
            patch.object(access_control.st, "title"),
            patch.object(access_control.st, "write"),
            patch.object(access_control.st, "form", return_value=form),
            patch.object(access_control.st, "text_input", return_value=""),
            patch.object(access_control.st, "form_submit_button", return_value=False),
        ):
            self.assertFalse(access_control.require_site_access())

        self.assertNotIn(access_control.SESSION_CODE_HASH_KEY, session_state)
        self.assertIsNone(access_control.get_authenticated_cbs_team_id())

    def test_sign_out_clears_session_code_hash(self):
        session_state = {
            access_control.SESSION_CODE_HASH_KEY: "existing-hash",
        }
        with patch.object(access_control.st, "session_state", session_state):
            access_control._sign_out()

        self.assertNotIn(access_control.SESSION_CODE_HASH_KEY, session_state)


if __name__ == "__main__":
    unittest.main()
