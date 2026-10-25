"""Confirmation-gated ESPN lineup submission."""

from __future__ import annotations

from datetime import datetime, timezone

import requests
from espn_api.football import League

from services.espn_afs_automation import (
    ESPNLineupAutomationError,
    WRITE_HEADERS,
    WRITE_URL,
    _lineup_fingerprint,
    _load_schedule,
    _owned_team,
    _verify_lineup,
    build_lineup_changes,
    build_transaction_payload,
)


class ESPNLineupSubmissionError(RuntimeError):
    """Raised when an ESPN lineup cannot safely be submitted or verified."""


def _http_status_message(error: requests.RequestException) -> str:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    return f" (HTTP {status_code})" if status_code is not None else ""


def _http_error_detail(error: requests.HTTPError) -> str:
    response = error.response
    if response is None:
        return ""

    try:
        payload = response.json()
    except ValueError:
        return ""

    if not isinstance(payload, dict):
        return ""

    details = []
    for key in ("message", "messages", "error", "errors", "detail", "details"):
        value = payload.get(key)
        if isinstance(value, str):
            details.append(value)
        elif isinstance(value, list):
            details.extend(item for item in value if isinstance(item, str))
    detail = " ".join(" ".join(details).split())[:400]
    return f" ESPN detail: {detail}" if detail else ""


def build_espn_lineup_proposal(league, team) -> dict:
    try:
        schedule = _load_schedule(league.year)
        expected_slots, changes = build_lineup_changes(
            league,
            team,
            schedule,
            datetime.now(timezone.utc),
        )
    except ESPNLineupAutomationError as exc:
        raise ESPNLineupSubmissionError(str(exc)) from exc
    except requests.RequestException as exc:
        raise ESPNLineupSubmissionError(
            "Could not load the ESPN schedule; no changes were sent."
        ) from exc

    return {
        "team_id": int(team.team_id),
        "fingerprint": _lineup_fingerprint(team),
        "expected_slots": expected_slots,
        "changes": changes,
    }


def apply_confirmed_espn_lineup(
    league_config: dict,
    team_id: int,
    expected_fingerprint: tuple[tuple[int, int], ...],
    expected_slots: dict[int, int],
    expected_changes: list[dict[str, int]],
) -> None:
    swid = str(league_config.get("swid") or "").strip()
    espn_s2 = str(league_config.get("espn_s2") or "").strip()
    if not swid or not espn_s2:
        raise ESPNLineupSubmissionError(
            "ESPN credentials are missing; no changes were sent."
        )
    if not expected_changes:
        raise ESPNLineupSubmissionError(
            "The current lineup already matches the optimized lineup."
        )

    try:
        league = League(
            league_id=league_config["league_id"],
            year=league_config["year"],
            swid=swid,
            espn_s2=espn_s2,
        )
    except requests.RequestException as exc:
        raise ESPNLineupSubmissionError(
            "Could not refresh the ESPN roster before submission; no lineup "
            "changes were sent."
        ) from exc

    team = _owned_team(league, swid)
    if int(team.team_id) != int(team_id):
        raise ESPNLineupSubmissionError(
            "The authenticated team changed; refresh the preview before "
            "submitting."
        )
    if _lineup_fingerprint(team) != expected_fingerprint:
        raise ESPNLineupSubmissionError(
            "The ESPN roster changed after the preview; refresh it before "
            "submitting."
        )

    try:
        schedule = _load_schedule(league_config["year"])
    except requests.RequestException as exc:
        raise ESPNLineupSubmissionError(
            "Could not refresh the ESPN schedule before submission; no "
            "lineup changes were sent."
        ) from exc

    try:
        current_slots, current_changes = build_lineup_changes(
            league,
            team,
            schedule,
            datetime.now(timezone.utc),
        )
        if (
            current_slots != expected_slots
            or current_changes != expected_changes
        ):
            raise ESPNLineupSubmissionError(
                "The optimized lineup or player lock status changed after "
                "the preview; refresh it before submitting."
            )

        payload = build_transaction_payload(
            int(team.team_id),
            int(league.nfl_week),
            swid,
            current_changes,
        )
    except ESPNLineupAutomationError as exc:
        raise ESPNLineupSubmissionError(str(exc)) from exc

    try:
        response = requests.post(
            WRITE_URL.format(
                year=league_config["year"],
                league_id=league_config["league_id"],
            ),
            json=payload,
            cookies={"SWID": swid, "espn_s2": espn_s2},
            headers=WRITE_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ESPNLineupSubmissionError(
            "ESPN responded"
            f"{_http_status_message(exc)} to the lineup submission."
            f"{_http_error_detail(exc)} "
            "Check your ESPN roster before retrying."
        ) from exc
    except requests.RequestException as exc:
        raise ESPNLineupSubmissionError(
            "The lineup submission could not be confirmed"
            f"{_http_status_message(exc)}. ESPN may have accepted it; check "
            "your ESPN roster before retrying."
        ) from exc

    try:
        _verify_lineup(league_config, swid, current_slots)
    except requests.RequestException as exc:
        raise ESPNLineupSubmissionError(
            "ESPN received the lineup submission, but the verification "
            f"request failed{_http_status_message(exc)}. Check your ESPN "
            "roster before retrying."
        ) from exc
    except ESPNLineupSubmissionError:
        raise
    except ESPNLineupAutomationError as exc:
        raise ESPNLineupSubmissionError(str(exc)) from exc
