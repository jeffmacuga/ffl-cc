import unittest
from unittest.mock import patch

import pandas as pd

from pages import lineup_preview, rosters, trade_analyzer


class CBSTeamPrivacyTests(unittest.TestCase):
    def test_roster_page_loads_all_cbs_teams(self):
        roster = pd.DataFrame([
            {"player_name": "League Player", "position": "QB"},
        ])
        teams = pd.DataFrame([
            {"provider_team_id": "101", "team_name": "Member Team"},
            {"provider_team_id": "102", "team_name": "Another Team"},
        ])

        with (
            patch.object(rosters, "get_cbs_teams", return_value=teams),
            patch.object(rosters, "get_cbs_roster", return_value=roster) as load_roster,
            patch.object(rosters, "format_last_data_sync", return_value=""),
            patch.object(rosters.st, "header"),
            patch.object(rosters.st, "caption"),
            patch.object(rosters.st, "dataframe") as show_dataframe,
            patch.object(rosters.st, "selectbox", return_value="Member Team") as show_team_picker,
        ):
            rosters.show_team_rosters({"platform": "CBS"}, "CBS")

        load_roster.assert_called_once_with("101")
        show_dataframe.assert_called_once()
        show_team_picker.assert_called_once()

    def test_cbs_lineup_preview_uses_only_the_member_assigned_team(self):
        with (
            patch.object(
                lineup_preview,
                "get_authenticated_cbs_team_id",
                return_value="101",
            ),
            patch.object(lineup_preview.st, "session_state", {}),
            patch.object(lineup_preview.st, "button", return_value=False),
            patch.object(lineup_preview.st, "selectbox") as show_team_picker,
            patch.object(lineup_preview.st, "multiselect", return_value=[]),
            patch.object(lineup_preview.st, "caption"),
            patch.object(lineup_preview.st, "write"),
            patch.object(lineup_preview.st, "warning"),
            patch.object(lineup_preview, "fetch_cbs_team_roster") as fetch_roster,
            patch.object(
                lineup_preview,
                "_load_espn_projection_lookups",
                return_value={},
            ),
            patch.object(
                lineup_preview,
                "build_cbs_projection_lookup",
                return_value={},
            ),
            patch.object(
                lineup_preview,
                "optimize_cbs_lineup",
                return_value={"complete": False, "missing_slots": []},
            ),
            patch.object(lineup_preview, "_show_fantasypros_decision_center"),
            patch.object(
                lineup_preview,
                "format_sync_timestamp",
                return_value="",
            ),
        ):
            fetch_roster.return_value = {
                "team_id": "101",
                "team_name": "Member Team",
                "players": [],
                "week": 1,
                "lineup_status": "",
                "synced_at": "2026-11-18T00:00:00+00:00",
            }
            lineup_preview.show_cbs_lineup_preview()

        fetch_roster.assert_called_once_with("101")
        show_team_picker.assert_not_called()

    def test_cbs_trade_analyzer_does_not_load_rosters(self):
        with (
            patch.object(trade_analyzer.st, "header"),
            patch.object(trade_analyzer.st, "caption"),
            patch.object(trade_analyzer.st, "info") as show_info,
        ):
            trade_analyzer.show_trade_analyzer({"platform": "CBS"})

        show_info.assert_called_once()
        self.assertIn("both teams' rosters", show_info.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
