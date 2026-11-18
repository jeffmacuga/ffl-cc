import unittest

from services.cbs_lineup_optimizer import LINEUP_SLOTS, optimize_cbs_lineup


def make_player(player_id, name, position, slot, status, projection):
    return {
        "provider_player_id": str(player_id),
        "player_name": name,
        "position": position,
        "eligible_positions": position,
        "roster_position": slot,
        "roster_status": status,
        "projected_points": projection,
        "is_locked": "0",
    }


class CBSLineupOptimizerTests(unittest.TestCase):
    def setUp(self):
        self.roster = [
            make_player(1, "Starter QB", "QB", "QB", "A", 10),
            make_player(2, "Reserve QB", "QB", "QB", "RS", 20),
            make_player(3, "RB One", "RB", "RB", "A", 10),
            make_player(4, "RB Two", "RB", "RB", "A", 9),
            make_player(5, "RB Three", "RB", "RB", "RS", 8),
            make_player(6, "WR One", "WR", "WR-TE", "A", 10),
            make_player(7, "WR Two", "WR", "WR-TE", "A", 9),
            make_player(8, "TE One", "TE", "WR-TE", "A", 8),
            make_player(9, "Flex WR", "WR", "RB-WR-TE", "A", 7),
            make_player(10, "Kicker", "K", "K", "A", 6),
            make_player(11, "Defense", "DST", "DST", "A", 5),
            make_player(12, "Injured RB", "RB", "RB", "I", 100),
        ]

    def test_builds_nine_player_lineup_with_one_qb_and_two_flex_slots(self):
        result = optimize_cbs_lineup(self.roster)

        self.assertTrue(result["complete"])
        self.assertEqual(len(result["lineup"]), 9)
        self.assertEqual(len(LINEUP_SLOTS), 9)
        self.assertEqual(result["projected_points"], 87)
        self.assertEqual(
            {player["slot"] for player in result["lineup"]},
            {
                "QB", "RB1", "RB2", "WR-TE1", "WR-TE2",
                "SUPER FLEX", "FLEX", "K", "DST",
            },
        )
        super_flex = next(
            player for player in result["lineup"]
            if player["slot"] == "SUPER FLEX"
        )
        self.assertEqual(super_flex["position"], "QB")
        moves_by_player = {
            move["player"]: move for move in result["moves"]
        }
        self.assertEqual(
            moves_by_player["Reserve QB"]["suggested_assignment"],
            "SUPER FLEX",
        )
        self.assertEqual(
            moves_by_player["Reserve QB"]["suggested_roster_position"],
            "QB",
        )
        self.assertEqual(
            moves_by_player["RB Three"]["suggested_assignment"],
            "FLEX",
        )
        self.assertEqual(
            moves_by_player["RB Three"]["suggested_roster_position"],
            "RB-WR-TE",
        )
        self.assertIn(
            "Reserve QB",
            {player["player"] for player in result["lineup"]},
        )
        self.assertNotIn(
            "Injured RB",
            {player["player"] for player in result["lineup"]},
        )

    def test_respects_flex_eligibility_and_player_uniqueness(self):
        result = optimize_cbs_lineup(self.roster)
        player_ids = [player["player_id"] for player in result["lineup"]]

        self.assertEqual(len(player_ids), len(set(player_ids)))
        flex = next(
            player for player in result["lineup"]
            if player["slot"] == "FLEX"
        )
        self.assertIn(flex["position"], {"RB", "WR", "TE"})
        self.assertNotEqual(flex["position"], "QB")

    def test_reports_incomplete_lineup_when_required_position_is_missing(self):
        roster = [
            player
            for player in self.roster
            if player["position"] != "DST"
        ]

        result = optimize_cbs_lineup(roster)

        self.assertFalse(result["complete"])
        self.assertEqual(result["lineup"], [])
        self.assertEqual(result["missing_slots"], ["DST"])

    def test_super_flex_can_be_filled_by_a_non_quarterback(self):
        roster = [
            player for player in self.roster
            if player["player_name"] != "Reserve QB"
        ]

        result = optimize_cbs_lineup(roster)

        self.assertTrue(result["complete"])
        super_flex = next(
            player for player in result["lineup"]
            if player["slot"] == "SUPER FLEX"
        )
        self.assertIn(super_flex["position"], {"RB", "WR", "TE"})
        self.assertNotEqual(super_flex["player"], "Starter QB")

    def test_current_illegal_lineup_status_does_not_block_optimization(self):
        result = optimize_cbs_lineup(self.roster)

        self.assertTrue(result["complete"])
        self.assertEqual(result["missing_slots"], [])

    def test_missing_projection_is_reported_without_using_average_points(self):
        self.roster[0]["projected_points"] = None
        self.roster[0]["average_points"] = 30

        result = optimize_cbs_lineup(self.roster)

        self.assertTrue(result["complete"])
        self.assertEqual(result["missing_projection_count"], 1)
        quarterback = next(
            player for player in result["lineup"] if player["slot"] == "QB"
        )
        self.assertEqual(quarterback["player"], "Reserve QB")

    def test_average_fallback_changes_score_and_can_change_lineup(self):
        self.roster[0]["projected_points"] = None
        self.roster[0]["average_points"] = 30

        projections_only = optimize_cbs_lineup(self.roster)
        with_average_fallback = optimize_cbs_lineup(
            self.roster,
            allow_average_fallback=True,
        )

        self.assertEqual(projections_only["projected_points"], 85)
        self.assertEqual(with_average_fallback["projected_points"], 107)
        self.assertEqual(with_average_fallback["average_fallback_count"], 1)
        self.assertEqual(
            next(
                player for player in with_average_fallback["lineup"]
                if player["slot"] == "QB"
            )["player"],
            "Starter QB",
        )

    def test_keeps_locked_players_in_place_and_moves_unlocked_players(self):
        roster = [dict(player) for player in self.roster]
        next(
            player for player in roster
            if player["player_name"] == "RB One"
        )["is_locked"] = "1"
        next(
            player for player in roster
            if player["player_name"] == "RB Three"
        )["projected_points"] = 30

        result = optimize_cbs_lineup(roster)

        self.assertTrue(result["complete"])
        self.assertNotIn("3", {move["player_id"] for move in result["moves"]})
        self.assertTrue(
            all(move["is_locked"] == "0" for move in result["moves"])
        )
        self.assertIn(
            "3",
            {player["player_id"] for player in result["lineup"]},
        )
        self.assertIn("5", {move["player_id"] for move in result["moves"]})

    def test_keeps_unknown_lock_status_players_in_place(self):
        roster = [dict(player) for player in self.roster]
        roster[0]["is_locked"] = None
        roster[1]["projected_points"] = 50

        result = optimize_cbs_lineup(roster)

        self.assertTrue(result["complete"])
        self.assertIn(
            "1",
            {player["player_id"] for player in result["lineup"]},
        )
        self.assertNotIn("1", {move["player_id"] for move in result["moves"]})


if __name__ == "__main__":
    unittest.main()
