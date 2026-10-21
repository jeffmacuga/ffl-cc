"""Scheduled, fail-closed lineup automation for the ESPN AFS league."""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from espn_api.football import League
from espn_api.football.constant import POSITION_MAP

from config import LEAGUES
from optimizer import get_optimal_lineup


EASTERN = ZoneInfo("America/New_York")
REFRESH_OFFSETS = (3, 2, 1)
SCHEDULE_WINDOW = timedelta(minutes=31)
WRITE_URL = (
    "https://lm-api-writes.fantasy.espn.com/apis/v3/games/ffl/"
    "seasons/{year}/segments/0/leagues/{league_id}/transactions/"
)
WRITE_HEADERS = {
    "Content-Type": "application/json",
    "x-fantasy-source": "kona",
    "x-fantasy-platform": "espn-fantasy-web",
}
RESERVE_SLOT_IDS = {20, 21, 24, 25}
POSITION_NAME_TO_ID = {
    label: slot_id
    for slot_id, label in POSITION_MAP.items()
    if isinstance(slot_id, int)
}


class ESPNLineupAutomationError(RuntimeError):
    """Raised when an ESPN lineup cannot be changed or safely verified."""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("The automation clock must include a timezone.")
    return value.astimezone(timezone.utc)


def _scheduled_games(schedule_data: dict, game_day: date) -> list[datetime]:
    pro_teams = schedule_data.get("settings", {}).get("proTeams")
    if not isinstance(pro_teams, list):
        raise ESPNLineupAutomationError(
            "ESPN's professional schedule is missing its team list."
        )

    game_times: dict[str, datetime] = {}
    has_unknown_start = False
    for pro_team in pro_teams:
        periods = pro_team.get("proGamesByScoringPeriod", {})
        if not isinstance(periods, dict):
            continue
        for games in periods.values():
            if not isinstance(games, list):
                continue
            for game in games:
                try:
                    kickoff = datetime.fromtimestamp(
                        int(game["date"]) / 1000,
                        timezone.utc,
                    ).astimezone(EASTERN)
                except (KeyError, TypeError, ValueError, OverflowError) as exc:
                    raise ESPNLineupAutomationError(
                        "ESPN returned a game without a valid kickoff time."
                    ) from exc
                if kickoff.date() != game_day:
                    continue
                if game.get("startTimeTBD"):
                    has_unknown_start = True
                else:
                    game_times[str(game.get("id") or game["date"])] = kickoff

    if has_unknown_start:
        raise ESPNLineupAutomationError(
            "At least one game today has an unconfirmed kickoff time; "
            "the automated schedule was skipped."
        )
    return list(game_times.values())


def get_first_kickoff(
    schedule_data: dict,
    game_day: date,
) -> datetime | None:
    games = _scheduled_games(schedule_data, game_day)
    return min(games) if games else None


def get_refresh_phase(
    schedule_data: dict,
    now: datetime,
) -> tuple[str, datetime] | None:
    now_utc = _as_utc(now)
    now_eastern = now_utc.astimezone(EASTERN)
    kickoff = get_first_kickoff(schedule_data, now_eastern.date())
    if kickoff is None:
        return None

    candidates = []
    for hours_before in REFRESH_OFFSETS:
        target = kickoff - timedelta(hours=hours_before)
        time_until_target = target.astimezone(timezone.utc) - now_utc
        if timedelta(0) <= time_until_target <= SCHEDULE_WINDOW:
            candidates.append((time_until_target, f"{hours_before}h", target))
    if not candidates:
        return None

    _, phase, kickoff_target = min(candidates)
    return phase, kickoff_target


def _slot_id(position: str) -> int:
    normalized = str(position).strip().upper()
    if normalized == "DST":
        normalized = "D/ST"
    if normalized == "FLEX":
        normalized = "RB/WR/TE"
    slot_id = POSITION_NAME_TO_ID.get(normalized)
    if slot_id is None:
        raise ESPNLineupAutomationError(
            f"The optimizer selected an unsupported ESPN lineup slot: "
            f"{position!r}."
        )
    return slot_id


def _optimizer_slot_counts(lineup: dict) -> Counter:
    counts = Counter()
    for slot in lineup:
        base_slot = re.sub(r"\d+$", "", str(slot)).upper()
        counts[_slot_id(base_slot)] += 1
    return counts


def _expected_active_slot_counts(league) -> Counter:
    slot_counts = getattr(league.settings, "position_slot_counts", None)
    if not isinstance(slot_counts, dict) or not slot_counts:
        raise ESPNLineupAutomationError(
            "ESPN did not provide lineup requirements for this league."
        )

    counts = Counter()
    for position, count in slot_counts.items():
        try:
            count = int(count)
        except (TypeError, ValueError) as exc:
            raise ESPNLineupAutomationError(
                "ESPN returned an invalid lineup requirement."
            ) from exc
        if count <= 0:
            continue
        slot_id = _slot_id(position)
        if slot_id not in RESERVE_SLOT_IDS:
            counts[slot_id] += count
    return counts


def _current_slot_id(player) -> int:
    slot_id = POSITION_NAME_TO_ID.get(
        str(getattr(player, "lineupSlot", "")).strip().upper()
    )
    if slot_id is None:
        raise ESPNLineupAutomationError(
            f"ESPN did not provide a recognized lineup slot for "
            f"{getattr(player, 'name', 'a rostered player')}."
        )
    return slot_id


def _team_game_times(
    schedule_data: dict,
    scoring_period: int,
) -> dict[str, datetime | None]:
    pro_teams = schedule_data.get("settings", {}).get("proTeams")
    if not isinstance(pro_teams, list):
        raise ESPNLineupAutomationError(
            "ESPN's professional schedule is missing its team list."
        )

    game_times = {}
    period = str(scoring_period)
    for pro_team in pro_teams:
        abbrev = pro_team.get("abbrev")
        games = pro_team.get("proGamesByScoringPeriod", {}).get(period, [])
        if not abbrev or not isinstance(games, list) or not games:
            continue
        game = games[0]
        if game.get("startTimeTBD"):
            game_times[str(abbrev).upper()] = None
            continue
        try:
            game_times[str(abbrev).upper()] = datetime.fromtimestamp(
                int(game["date"]) / 1000,
                timezone.utc,
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ESPNLineupAutomationError(
                "ESPN returned an invalid game time for a rostered player's team."
            ) from exc
    return game_times


def build_lineup_changes(
    league,
    team,
    schedule_data: dict,
    now: datetime,
) -> tuple[dict[int, int], list[dict[str, int]]]:
    lineup_result = get_optimal_lineup(team)
    if isinstance(lineup_result, tuple):
        lineup_result = lineup_result[0]
    if not isinstance(lineup_result, dict):
        raise ESPNLineupAutomationError(
            "The optimizer did not return a lineup."
        )

    actual_counts = _optimizer_slot_counts(lineup_result)
    required_counts = _expected_active_slot_counts(league)
    if actual_counts != required_counts:
        raise ESPNLineupAutomationError(
            "The optimizer's lineup slots do not match the AFS league "
            "requirements; no changes were sent."
        )

    roster = getattr(team, "roster", None)
    if not isinstance(roster, list) or not roster:
        raise ESPNLineupAutomationError(
            "ESPN did not return a usable roster."
        )

    selected_players = {}
    for slot, entry in lineup_result.items():
        player = entry.get("player_obj") if isinstance(entry, dict) else None
        player_id = getattr(player, "playerId", None)
        if player is None or player_id is None or player_id in selected_players:
            raise ESPNLineupAutomationError(
                "The optimized lineup contains a missing or duplicate player."
            )
        selected_players[player_id] = _slot_id(
            re.sub(r"\d+$", "", str(slot))
        )

    game_times = _team_game_times(schedule_data, league.nfl_week)
    now_utc = _as_utc(now)
    target_slots: dict[int, int] = {}
    changes = []
    seen_ids = set()

    for player in roster:
        player_id = getattr(player, "playerId", None)
        if player_id is None or player_id in seen_ids:
            raise ESPNLineupAutomationError(
                "ESPN returned a roster with missing or duplicate player IDs."
            )
        seen_ids.add(player_id)
        current_slot = _current_slot_id(player)
        if player_id in selected_players:
            target_slot = selected_players[player_id]
            eligible_slots = {
                _slot_id(position)
                for position in getattr(player, "eligibleSlots", [])
            }
            if target_slot not in eligible_slots:
                raise ESPNLineupAutomationError(
                    f"The optimizer selected a slot that "
                    f"{getattr(player, 'name', 'a player')} is not eligible for."
                )
        elif current_slot in RESERVE_SLOT_IDS and current_slot != 20:
            target_slot = current_slot
        else:
            target_slot = 20

        target_slots[int(player_id)] = target_slot
        if current_slot == target_slot:
            continue

        player_team = str(getattr(player, "proTeam", "")).upper()
        player_kickoff = game_times.get(player_team)
        if player_team in game_times and (
            player_kickoff is None or player_kickoff <= now_utc
        ):
            raise ESPNLineupAutomationError(
                "A proposed move would change a player whose NFL game has "
                "started or has an unconfirmed kickoff; no changes were sent."
            )
        changes.append({
            "playerId": int(player_id),
            "type": "LINEUP",
            "fromLineupSlotId": current_slot,
            "toLineupSlotId": target_slot,
            "fromTeamId": 0,
            "toTeamId": 0,
        })

    if len(seen_ids) != len(roster):
        raise ESPNLineupAutomationError(
            "ESPN returned an incomplete roster; no changes were sent."
        )
    return target_slots, changes


def build_transaction_payload(
    team_id: int,
    scoring_period: int,
    member_id: str,
    changes: list[dict[str, int]],
) -> dict:
    if not changes:
        raise ESPNLineupAutomationError(
            "The current lineup already matches the optimized lineup."
        )
    return {
        "isLeagueManager": False,
        "teamId": int(team_id),
        "type": "ROSTER",
        "scoringPeriodId": int(scoring_period),
        "executionType": "EXECUTE",
        "memberId": member_id,
        "items": changes,
    }


def _owned_team(league, swid: str):
    owner_id = swid.strip().strip("{}").casefold()
    matches = [
        team
        for team in league.teams
        if any(
            str(owner.get("id") or "").strip().strip("{}").casefold()
            == owner_id
            for owner in getattr(team, "owners", [])
        )
    ]
    if len(matches) != 1:
        raise ESPNLineupAutomationError(
            "The authenticated ESPN account did not resolve to exactly one "
            "AFS team; no changes were sent."
        )
    return matches[0]


def _afs_config(require_credentials: bool = True) -> dict:
    matches = [
        league
        for league in LEAGUES
        if league.get("name") == "AFS" and league.get("platform") == "ESPN"
    ]
    if len(matches) != 1:
        raise ESPNLineupAutomationError(
            "The ESPN AFS league must be configured exactly once."
        )
    config = dict(matches[0])
    config["swid"] = os.environ.get("ESPN_SWID", "").strip()
    config["espn_s2"] = os.environ.get("ESPN_S2", "").strip()
    if require_credentials and (not config["swid"] or not config["espn_s2"]):
        raise ESPNLineupAutomationError(
            "Configure ESPN_SWID and ESPN_S2 as GitHub Actions secrets."
        )
    return config


def _load_schedule(year: int) -> dict:
    response = requests.get(
        f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
        f"seasons/{year}",
        params={"view": "proTeamSchedules_wl"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ESPNLineupAutomationError(
            "ESPN returned an unexpected professional schedule response."
        )
    return payload


def _lineup_fingerprint(team) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(
        (int(player.playerId), _current_slot_id(player))
        for player in team.roster
    ))


def _verify_lineup(league_config: dict, swid: str, expected_slots: dict[int, int]):
    refreshed = League(
        league_id=league_config["league_id"],
        year=league_config["year"],
        swid=swid,
        espn_s2=league_config["espn_s2"],
    )
    team = _owned_team(refreshed, swid)
    actual_slots = {
        int(player.playerId): _current_slot_id(player)
        for player in team.roster
    }
    if any(
        actual_slots.get(player_id) != target_slot
        for player_id, target_slot in expected_slots.items()
    ):
        raise ESPNLineupAutomationError(
            "ESPN accepted the request but the refreshed roster does not "
            "match the proposed lineup."
        )


def run_scheduled_refresh(
    now: datetime | None = None,
    manual: bool = False,
    manual_submit: bool = False,
) -> str:
    now = now or datetime.now(timezone.utc)
    config = _afs_config(require_credentials=False)
    schedule_data = _load_schedule(config["year"])
    if manual:
        kickoff = get_first_kickoff(
            schedule_data,
            _as_utc(now).astimezone(EASTERN).date(),
        )
        if kickoff is None:
            print("There is no confirmed NFL kickoff scheduled for today.")
            return "skipped"
        if manual_submit:
            time_until_kickoff = kickoff.astimezone(timezone.utc) - _as_utc(now)
            if not timedelta(0) < time_until_kickoff <= timedelta(hours=2):
                raise ESPNLineupAutomationError(
                    "Manual submission is allowed only when today's first "
                    "kickoff is within the next two hours."
                )
            phase = ("1h", kickoff - timedelta(hours=1))
        else:
            phase = ("manual", kickoff)
    else:
        phase = get_refresh_phase(schedule_data, now)
    if phase is None:
        print("No AFS lineup refresh is due in this scheduled window.")
        return "skipped"

    phase_name, _ = phase
    config = _afs_config()
    league = League(
        league_id=config["league_id"],
        year=config["year"],
        swid=config["swid"],
        espn_s2=config["espn_s2"],
    )
    team = _owned_team(league, config["swid"])
    expected_slots, changes = build_lineup_changes(
        league,
        team,
        schedule_data,
        now,
    )
    print(
        f"AFS {phase_name} refresh completed for "
        f"{len(team.roster)} rostered players; "
        f"{len(changes)} lineup move(s) proposed."
    )

    if phase_name != "1h" or not changes:
        return "refreshed"
    if os.environ.get("ESPN_AUTO_SUBMIT", "").strip().lower() != "true":
        print("Lineup submission is disabled; no ESPN write was sent.")
        return "dry-run"

    latest = League(
        league_id=config["league_id"],
        year=config["year"],
        swid=config["swid"],
        espn_s2=config["espn_s2"],
    )
    latest_team = _owned_team(latest, config["swid"])
    if _lineup_fingerprint(team) != _lineup_fingerprint(latest_team):
        raise ESPNLineupAutomationError(
            "The AFS roster changed after optimization; no lineup was sent."
        )
    expected_slots, changes = build_lineup_changes(
        latest,
        latest_team,
        schedule_data,
        now,
    )
    if not changes:
        print("The latest AFS lineup already matches the optimizer.")
        return "unchanged"

    payload = build_transaction_payload(
        int(latest_team.team_id),
        int(latest.nfl_week),
        config["swid"],
        changes,
    )
    response = requests.post(
        WRITE_URL.format(
            year=config["year"],
            league_id=config["league_id"],
        ),
        json=payload,
        cookies={"SWID": config["swid"], "espn_s2": config["espn_s2"]},
        headers=WRITE_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    _verify_lineup(config, config["swid"], expected_slots)
    print("AFS lineup submission was confirmed by a fresh ESPN roster read.")
    return "submitted"
