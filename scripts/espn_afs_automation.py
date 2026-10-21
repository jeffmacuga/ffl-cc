import argparse
import sys

import requests

from services.espn_afs_automation import (
    ESPNLineupAutomationError,
    run_scheduled_refresh,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Run a manual refresh outside the scheduled kickoff windows.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Allow a manual submission when today's first kickoff is within two hours.",
    )
    args = parser.parse_args()
    if args.submit and not args.manual:
        parser.error("--submit requires --manual.")

    try:
        run_scheduled_refresh(
            manual=args.manual,
            manual_submit=args.submit,
        )
    except (ESPNLineupAutomationError, requests.RequestException) as exc:
        print(f"ESPN AFS lineup automation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
