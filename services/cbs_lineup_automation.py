"""Scheduled, fail-closed lineup automation for the CBS league."""

from __future__ import annotations

import os

from services.cbs_lineup_optimizer import optimize_cbs_lineup
from services.cbs_lineup_submission import (
    CBSLineupError,
    apply_confirmed_lineup,
    fetch_my_cbs_roster,
)


def run_cbs_lineup_refresh(
    *,
    manual: bool = False,
    manual_submit: bool = False,
) -> str:
    if manual_submit and not manual:
        raise CBSLineupError("Manual lineup submission requires manual mode.")

    roster = fetch_my_cbs_roster()
    result = optimize_cbs_lineup(roster["players"])
    if not result["complete"]:
        missing_slots = ", ".join(result["missing_slots"]) or "unknown"
        raise CBSLineupError(
            "CBS did not provide a complete legal lineup "
            f"(missing slots: {missing_slots}); no changes were sent."
        )

    moves = result["moves"]
    print(
        f"CBS week {roster['week']} refresh completed for "
        f"{len(roster['players'])} rostered players; "
        f"{len(moves)} lineup move(s) proposed."
    )
    if not moves:
        print("The current CBS lineup already matches the optimizer.")
        return "unchanged"

    should_submit = (
        manual_submit
        if manual
        else os.environ.get("CBS_AUTO_SUBMIT", "").strip().lower() == "true"
    )
    if not should_submit:
        if manual:
            print("Manual submission was not requested; no CBS write was sent.")
        else:
            print("CBS lineup submission is disabled; no changes were sent.")
        return "dry-run"

    apply_confirmed_lineup(
        expected_fingerprint=roster["fingerprint"],
        team_id=roster["team_id"],
        week=roster["week"],
        moves=moves,
    )
    print("CBS lineup submission was confirmed by a fresh roster read.")
    return "submitted"
