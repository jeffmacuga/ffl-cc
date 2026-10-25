from collections import Counter
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import services.espn_afs_automation as automation
from services.espn_afs_automation import (
    ESPNLineupAutomationError,
    build_lineup_changes,
    build_transaction_payload,
    get_first_kickoff,
    get_refresh_phase,
)


EASTERN = ZoneInfo("America/New_York")


def _game(game_id, kickoff, *, time_tbd=False):
    return {
        "id": game_id,
        "date": int(kickoff.timestamp() * 1000),
        "startTimeTBD": time_tbd,
    }


def _schedule_for(kickoffs):
    return {
        "settings": {
            "proTeams": [
                {
                    "abbrev": "BUF",
                    "proGamesByScoringPeriod": {
                        "1": [
                            _game(str(index), kickoff, time_tbd=time_tbd)
                            for index, (kickoff, time_tbd) in enumerate(kickoffs)
                        ]
                    },
                }
            ]
        }
    }


def _optimizer_roster():
    positions = [
        ("QB", "QB", ["QB"]),
        ("RB1", "RB", ["RB", "RB/WR/TE"]),
        ("RB2", "RB", ["RB", "RB/WR/TE"]),
        ("WR1", "WR", ["WR", "RB/WR/TE"]),
        ("WR2", "WR", ["WR", "RB/WR/TE"]),
        ("TE", "TE", ["TE", "RB/WR/TE"]),
        ("K", "K", ["K"]),
        ("DST", "D/ST", ["D/ST"]),
        ("LB", "LB", ["LB"]),
        ("DL", "DE", ["DE", "DL"]),
        ("DB", "S", ["S", "DB"]),
        ("FLEX", "RB", ["RB", "RB/WR/TE"]),
    ]
    roster = []
    for player_id, (_, position, eligible) in enumerate(positions, start=1):
        roster.append(SimpleNamespace(
            playerId=player_id,
            name=f"Player {player_id}",
            position=position,
            eligibleSlots=eligible,
            lineupSlot="BE",
            proTeam="BUF",
            projected_avg_points=20 - player_id,
            projected_points=0,
            avg_points=0,
            injuryStatus="",
        ))

    requirements = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "K": 1,
        "D/ST": 1,
        "LB": 1,
        "DL": 1,
        "DB": 1,
        "RB/WR/TE": 1,
    }
    team = SimpleNamespace(roster=roster)
    league = SimpleNamespace(
        nfl_week=1,
        settings=SimpleNamespace(position_slot_counts=requirements),
    )
    return league, team


class ESPNLineupAutomationTests(unittest.TestCase):
    def test_first_kickoff_deduplicates_teams_and_uses_eastern_date(self):
        thursday_kickoff = datetime(2026, 10, 22, 20, 15, tzinfo=EASTERN)
        data = _schedule_for([(thursday_kickoff, False)])
        data["settings"]["proTeams"].append(data["settings"]["proTeams"][0])

        self.assertEqual(
            get_first_kickoff(data, date(2026, 10, 22)),
            thursday_kickoff,
        )

    def test_schedule_skips_day_with_unconfirmed_kickoff(self):
        kickoff = datetime(2026, 10, 22, 20, 15, tzinfo=EASTERN)
        data = _schedule_for([
            (kickoff - timedelta(hours=2), True),
            (kickoff, False),
        ])

        with self.assertRaisesRegex(ESPNLineupAutomationError, "unconfirmed"):
            get_first_kickoff(data, date(2026, 10, 22))

    def test_refresh_phase_triggers_before_each_target_and_not_after(self):
        kickoff = datetime(2026, 10, 22, 20, 15, tzinfo=EASTERN)
        data = _schedule_for([(kickoff, False)])

        self.assertEqual(
            get_refresh_phase(
                data,
                datetime(2026, 10, 22, 17, 0, tzinfo=EASTERN),
            )[0],
            "3h",
        )
        self.assertEqual(
            get_refresh_phase(
                data,
                datetime(2026, 10, 22, 18, 0, tzinfo=EASTERN),
            )[0],
            "2h",
        )
        self.assertEqual(
            get_refresh_phase(
                data,
                datetime(2026, 10, 22, 19, 0, tzinfo=EASTERN),
            )[0],
            "1h",
        )
        self.assertIsNone(
            get_refresh_phase(
                data,
                datetime(2026, 10, 22, 19, 16, tzinfo=EASTERN),
            )
        )

    def test_builds_changes_only_for_complete_supported_lineup(self):
        league, team = _optimizer_roster()
        now = datetime(2026, 10, 22, 17, tzinfo=EASTERN)
        schedule = {
            "settings": {
                "proTeams": [
                    {
                        "abbrev": "BUF",
                        "proGamesByScoringPeriod": {
                            "1": [_game(1, now + timedelta(hours=3), time_tbd=False)]
                        },
                    }
                ]
            }
        }

        target_slots, changes = build_lineup_changes(
            league,
            team,
            schedule,
            now,
        )

        self.assertEqual(len(target_slots), len(team.roster))
        self.assertEqual(len(changes), 12)
        self.assertTrue(all(
            change["fromLineupSlotId"] == 20 for change in changes
        ))
        self.assertTrue(all(
            "fromTeamId" not in change and "toTeamId" not in change
            for change in changes
        ))
        self.assertEqual(Counter(target_slots.values()), Counter({
            0: 1,
            2: 2,
            4: 2,
            6: 1,
            17: 1,
            16: 1,
            10: 1,
            11: 1,
            14: 1,
            23: 1,
        }))

    def test_refuses_move_of_player_whose_game_has_started(self):
        league, team = _optimizer_roster()
        now = datetime(2026, 10, 22, 17, tzinfo=EASTERN)
        earlier_kickoff = now - timedelta(minutes=1)
        schedule = {
            "settings": {
                "proTeams": [
                    {
                        "abbrev": "BUF",
                        "proGamesByScoringPeriod": {
                            "1": [_game(1, earlier_kickoff, time_tbd=False)]
                        },
                    }
                ]
            }
        }

        with self.assertRaisesRegex(
            ESPNLineupAutomationError,
            "started",
        ):
            build_lineup_changes(league, team, schedule, now)

    def test_optimizer_benches_josh_allen_during_bills_bye_week(self):
        league, team = _optimizer_roster()
        league.nfl_week = 7
        now = datetime(2026, 10, 25, 10, tzinfo=EASTERN)
        bye_player = team.roster[0]
        bye_player.name = "Josh Allen"
        bye_player.proTeam = "BUF"
        bye_player.lineupSlot = "QB"
        bye_player.projected_avg_points = 100
        for player in team.roster:
            if player is not bye_player:
                player.proTeam = "NYG"
        replacement = SimpleNamespace(
            playerId=13,
            name="Replacement QB",
            position="QB",
            eligibleSlots=["QB"],
            lineupSlot="BE",
            proTeam="NYG",
            projected_avg_points=10,
            projected_points=0,
            avg_points=0,
            injuryStatus="",
        )
        team.roster.append(replacement)
        schedule = {
            "settings": {
                "proTeams": [
                    {
                        "abbrev": "BUF",
                        "byeWeek": 7,
                        "proGamesByScoringPeriod": {},
                    },
                    {
                        "abbrev": "NYG",
                        "proGamesByScoringPeriod": {
                            "7": [_game(1, now + timedelta(hours=3))]
                        },
                    },
                ]
            }
        }

        target_slots, changes = build_lineup_changes(
            league,
            team,
            schedule,
            now,
        )

        self.assertEqual(target_slots[bye_player.playerId], 20)
        self.assertEqual(target_slots[replacement.playerId], 0)
        self.assertTrue(any(
            change["playerId"] == bye_player.playerId
            and change["toLineupSlotId"] == 20
            for change in changes
        ))

    def test_refuses_lineup_that_does_not_match_afs_settings(self):
        league, team = _optimizer_roster()
        league.settings.position_slot_counts["QB"] = 2
        schedule = _schedule_for([
            (datetime(2026, 10, 22, 20, 15, tzinfo=EASTERN), False)
        ])

        with self.assertRaisesRegex(ESPNLineupAutomationError, "requirements"):
            build_lineup_changes(
                league,
                team,
                schedule,
                datetime(2026, 10, 22, 17, tzinfo=EASTERN),
            )

    def test_builds_a_standard_espn_lineup_from_league_settings(self):
        league, team = _optimizer_roster()
        league.settings.position_slot_counts = {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "K": 1,
            "D/ST": 1,
            "RB/WR/TE": 1,
            "BE": 5,
            "Rookie": 1,
        }
        now = datetime(2026, 10, 22, 17, tzinfo=EASTERN)
        schedule = _schedule_for([
            (now + timedelta(hours=3), False)
        ])

        target_slots, _ = build_lineup_changes(
            league,
            team,
            schedule,
            now,
        )

        active_slot_ids = Counter(
            slot_id
            for slot_id in target_slots.values()
            if slot_id != 20
        )
        self.assertEqual(active_slot_ids, Counter({
            0: 1,
            2: 2,
            4: 2,
            6: 1,
            17: 1,
            16: 1,
            23: 1,
        }))

    def test_transaction_payload_has_only_required_lineup_write_fields(self):
        changes = [{
            "playerId": 101,
            "type": "LINEUP",
            "fromLineupSlotId": 20,
            "toLineupSlotId": 0,
        }]

        payload = build_transaction_payload(5, 8, "{member-id}", changes)

        self.assertEqual(payload, {
            "isLeagueManager": False,
            "teamId": 5,
            "type": "ROSTER",
            "scoringPeriodId": 8,
            "executionType": "EXECUTE",
            "memberId": "{member-id}",
            "items": changes,
        })

    def test_submission_stays_disabled_without_explicit_opt_in(self):
        league, team = _optimizer_roster()
        team.team_id = 7
        team.owners = [{"id": "member-id"}]
        league.teams = [team]
        now = datetime(2026, 10, 22, 19, tzinfo=EASTERN)
        schedule = _schedule_for([
            (now + timedelta(hours=1), False)
        ])

        with (
            patch.dict(
                "os.environ",
                {
                    "ESPN_SWID": "{member-id}",
                    "ESPN_S2": "test-cookie",
                    "ESPN_AUTO_SUBMIT": "",
                },
            ),
            patch.object(automation, "_load_schedule", return_value=schedule),
            patch.object(automation, "League", return_value=league),
            patch.object(automation.requests, "post") as post,
        ):
            result = automation.run_scheduled_refresh(now=now)

        self.assertEqual(result, "dry-run")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
