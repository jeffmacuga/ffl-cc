import unittest
from types import SimpleNamespace

from optimizer import calculate_player_score


class PlayerScoreTests(unittest.TestCase):
    def test_projection_only_does_not_use_average_points(self):
        player = SimpleNamespace(
            projected_avg_points=0,
            projected_points=0,
            avg_points=18,
        )

        self.assertEqual(
            calculate_player_score(player, allow_average_fallback=False),
            0,
        )

    def test_average_fallback_is_used_when_projection_is_unavailable(self):
        player = SimpleNamespace(
            projected_avg_points=0,
            projected_points=0,
            avg_points=18,
        )

        self.assertEqual(calculate_player_score(player), 18)

    def test_projection_takes_precedence_over_average_fallback(self):
        player = SimpleNamespace(
            projected_avg_points=0,
            projected_points=12,
            avg_points=18,
        )

        self.assertEqual(calculate_player_score(player), 12)


if __name__ == "__main__":
    unittest.main()
