import unittest
from types import SimpleNamespace

import pandas as pd

from pages.lineup_preview import (
    AFS_LINEUP_SLOT_ORDER,
    KICKBUTT_LINEUP_SLOT_ORDER,
    _build_cbs_current_lineup,
    _build_espn_current_lineup,
    _cbs_preview_needs_refresh,
    _sort_espn_lineup_preview,
)


class CurrentLineupTests(unittest.TestCase):
    def test_builds_espn_current_lineup_and_skips_ir_reserve(self):
        roster = [
            SimpleNamespace(name="Starter", lineupSlot="QB"),
            SimpleNamespace(name="Bench", lineupSlot="BE"),
            SimpleNamespace(name="Injured Reserve", lineupSlot="IR"),
        ]

        result = _build_espn_current_lineup(roster)

        self.assertEqual(result.to_dict("records"), [
            {"Slot": "QB", "Player": "Starter"},
            {"Slot": "BE", "Player": "Bench"},
        ])

    def test_builds_cbs_current_assignments(self):
        roster = [
            {
                "player_name": "Starter",
                "roster_status": "A",
                "roster_position": "WR-TE",
            },
            {
                "player_name": "Reserve",
                "roster_status": "RS",
                "roster_position": "QB",
            },
            {
                "player_name": "Injured",
                "roster_status": "I",
                "roster_position": "RB",
            },
        ]

        result = _build_cbs_current_lineup(roster)

        self.assertEqual(result.to_dict("records"), [
            {"Slot": "WR-TE", "Player": "Starter"},
            {"Slot": "Bench", "Player": "Reserve"},
            {"Slot": "Injured", "Player": "Injured"},
        ])


class ESPNLineupPreviewOrderTests(unittest.TestCase):
    def test_orders_afs_slots_as_requested_and_keeps_duplicate_slots_stable(self):
        frame = pd.DataFrame([
            {"Slot": "BE", "Player": "Bench"},
            {"Slot": "DST", "Player": "Defense"},
            {"Slot": "K", "Player": "Kicker"},
            {"Slot": "RB/WR/TE", "Player": "Flex"},
            {"Slot": "TE", "Player": "Tight End"},
            {"Slot": "WR", "Player": "WR 2"},
            {"Slot": "WR", "Player": "WR 1"},
            {"Slot": "RB", "Player": "RB 2"},
            {"Slot": "RB", "Player": "RB 1"},
            {"Slot": "QB", "Player": "Quarterback"},
        ])

        ordered = _sort_espn_lineup_preview(frame, AFS_LINEUP_SLOT_ORDER)

        self.assertEqual(ordered["Slot"].tolist(), [
            "QB",
            "RB",
            "RB",
            "WR",
            "WR",
            "TE",
            "RB/WR/TE",
            "K",
            "DST",
            "BE",
        ])
        self.assertEqual(ordered.loc[1:2, "Player"].tolist(), ["RB 2", "RB 1"])
        self.assertEqual(ordered.loc[3:4, "Player"].tolist(), ["WR 2", "WR 1"])
        self.assertEqual(ordered.iloc[-1]["Player"], "Bench")

    def test_orders_kickbutt_slots_as_requested_and_keeps_duplicate_slots_stable(self):
        frame = pd.DataFrame([
            {"Slot": "BE", "Player": "Bench"},
            {"Slot": "DB", "Player": "Defensive Back"},
            {"Slot": "LB", "Player": "Linebacker"},
            {"Slot": "DL", "Player": "Defensive Line"},
            {"Slot": "K", "Player": "Kicker"},
            {"Slot": "RB/WR/TE", "Player": "Flex"},
            {"Slot": "TE", "Player": "Tight End"},
            {"Slot": "WR", "Player": "WR 2"},
            {"Slot": "WR", "Player": "WR 1"},
            {"Slot": "RB", "Player": "RB 2"},
            {"Slot": "RB", "Player": "RB 1"},
            {"Slot": "QB", "Player": "Quarterback"},
        ])

        ordered = _sort_espn_lineup_preview(
            frame,
            KICKBUTT_LINEUP_SLOT_ORDER,
        )

        self.assertEqual(ordered["Slot"].tolist(), [
            "QB",
            "RB",
            "RB",
            "WR",
            "WR",
            "TE",
            "RB/WR/TE",
            "K",
            "DL",
            "LB",
            "DB",
            "BE",
        ])
        self.assertEqual(ordered.loc[1:2, "Player"].tolist(), ["RB 2", "RB 1"])
        self.assertEqual(ordered.loc[3:4, "Player"].tolist(), ["WR 2", "WR 1"])
        self.assertEqual(ordered.iloc[-1]["Player"], "Bench")


class CBSLineupPreviewCacheTests(unittest.TestCase):
    def test_refreshes_preview_without_sync_timestamp(self):
        preview = {"preview_requested_team": "6"}

        self.assertTrue(_cbs_preview_needs_refresh(preview, "6"))

    def test_keeps_preview_with_matching_team_and_sync_timestamp(self):
        preview = {
            "preview_requested_team": "6",
            "synced_at": "2026-10-25T07:00:00+00:00",
        }

        self.assertFalse(_cbs_preview_needs_refresh(preview, "6"))

    def test_refreshes_preview_for_different_team(self):
        preview = {
            "preview_requested_team": "6",
            "synced_at": "2026-10-25T07:00:00+00:00",
        }

        self.assertTrue(_cbs_preview_needs_refresh(preview, "8"))


if __name__ == "__main__":
    unittest.main()
