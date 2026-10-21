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

    def test_builds_nine_player_lineup_and_promotes_best_reserve(self):
        result = optimize_cbs_lineup(self.roster)

        self.assertTrue(result["complete"])
        self.assertEqual(len(result["lineup"]), 9)
        self.assertEqual(len(LINEUP_SLOTS), 9)
        self.assertEqual(result["projected_points"], 85)
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
            if player["slot"] == "RB-WR-TE"
        )
        self.assertIn(flex["position"], {"RB", "WR", "TE"})

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
        qb = next(player for player in result["lineup"] if player["slot"] == "QB")
        self.assertEqual(qb["player"], "Reserve QB")

    def test_average_fallback_changes_score_and_can_change_lineup(self):
        self.roster[0]["projected_points"] = None
        self.roster[0]["average_points"] = 30

        projections_only = optimize_cbs_lineup(self.roster)
        with_average_fallback = optimize_cbs_lineup(
            self.roster,
            allow_average_fallback=True,
        )

        self.assertEqual(projections_only["projected_points"], 85)
        self.assertEqual(with_average_fallback["projected_points"], 95)
        self.assertEqual(with_average_fallback["average_fallback_count"], 1)
        qb = next(
            player for player in with_average_fallback["lineup"]
            if player["slot"] == "QB"
        )
        self.assertEqual(qb["player"], "Starter QB")


if __name__ == "__main__":
    unittest.main()
