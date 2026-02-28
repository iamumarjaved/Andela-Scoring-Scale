#!/usr/bin/env python3
"""Backfill historical data day by day with rate-limit awareness."""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tracker.config import load_env
from scripts.daily_fetch import fetch_day, HEADERS


def main():
    parser = argparse.ArgumentParser(description="Backfill historical GitHub activity data")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--sleep", type=int, default=2, help="Seconds to sleep between days (rate limiting)")
    args = parser.parse_args()

    gh, sheets, config, base_repos, learners = load_env()
    print(f"Backfilling for {len(learners)} learners")

    ws = sheets.get_worksheet("Daily Raw Metrics")
    existing = ws.row_values(1) if ws.row_count > 0 else []
    if not existing or existing[0] != "Username":
        ws.update(values=[HEADERS], range_name="A1")

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now(timezone.utc)

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n--- Backfilling {date_str} ---")
        fetch_day(gh, sheets, ws, learners, base_repos, date_str)
        current += timedelta(days=1)

        if current <= end:
            print(f"  Sleeping {args.sleep}s to avoid rate limits...")
            time.sleep(args.sleep)

    print("\nBackfill complete.")


if __name__ == "__main__":
    main()
