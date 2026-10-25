import argparse
import sys

from playwright.sync_api import Error as PlaywrightError

from services.cbs_lineup_submission import CBSLineupError
from services.cbs_lineup_automation import run_cbs_lineup_refresh


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Run a manual CBS lineup refresh.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit the optimized lineup during a manual run.",
    )
    args = parser.parse_args()
    if args.submit and not args.manual:
        parser.error("--submit requires --manual.")

    try:
        run_cbs_lineup_refresh(
            manual=args.manual,
            manual_submit=args.submit,
        )
    except (CBSLineupError, PlaywrightError) as exc:
        print(f"CBS lineup automation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
