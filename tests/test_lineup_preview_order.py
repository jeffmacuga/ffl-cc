import unittest

import pandas as pd

from pages.lineup_preview import (
    AFS_LINEUP_SLOT_ORDER,
    KICKBUTT_LINEUP_SLOT_ORDER,
    _sort_espn_lineup_preview,
)


class ESPNLineupPreviewOrderTests(unittest.TestCase):
    def test_orders_afs_slots_as_requested_and_keeps_duplicate_slots_stable(self):
        frame = pd.DataFrame([
            {"Slot": "D/ST", "Player": "Defense"},
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
            "D/ST",
        ])
        self.assertEqual(ordered.loc[1:2, "Player"].tolist(), ["RB 2", "RB 1"])
        self.assertEqual(ordered.loc[3:4, "Player"].tolist(), ["WR 2", "WR 1"])

    def test_orders_kickbutt_slots_as_requested_and_keeps_duplicate_slots_stable(self):
        frame = pd.DataFrame([
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
        ])
        self.assertEqual(ordered.loc[1:2, "Player"].tolist(), ["RB 2", "RB 1"])
        self.assertEqual(ordered.loc[3:4, "Player"].tolist(), ["WR 2", "WR 1"])


if __name__ == "__main__":
    unittest.main()
