#!/usr/bin/env python3
"""Daily deep fetch orchestrator.

Runs the full daily pipeline: sheet structure setup, config defaults,
daily metrics fetch, sorting, leaderboard update, daily view, alerts,
and formatting. All logic lives in tracker submodules.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tracker.config import load_env
from tracker.constants import DAILY_HEADERS
from tracker.formatting import setup_sheet_structure, ensure_config_defaults, format_sheets, protect_sheets
from tracker.writers import (
    write_daily_metrics,
    sort_daily_raw_metrics,
    update_leaderboard,
    write_period_leaderboard,
    write_summary,
    write_daily_view,
    write_alerts,
    write_external_sheet,
)

fetch_day = write_daily_metrics

HEADERS = DAILY_HEADERS


def main():
    """Run the complete daily deep fetch pipeline."""
    gh, sheets, config, base_repos, learners = load_env()
    print(f"Daily deep fetch for {len(learners)} learners")

    setup_sheet_structure(sheets)
    ensure_config_defaults(sheets)

    ws = sheets.get_worksheet("Daily Raw Metrics")
    existing = ws.row_values(1) if ws.row_count > 0 else []
    if not existing or existing[0] != "Username":
        ws.update(values=[DAILY_HEADERS], range_name="A1")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    # Re-process yesterday to catch activity that happened after yesterday's run
    write_daily_metrics(gh, sheets, ws, learners, base_repos, yesterday)
    write_daily_metrics(gh, sheets, ws, learners, base_repos, today)

    sort_daily_raw_metrics(ws)

    leaderboard_rows = update_leaderboard(gh, sheets, learners, base_repos, config)

    today_dt = datetime.now(timezone.utc).date()

    # Weekly Leaderboard (Monday to today of current week)
    monday = today_dt - timedelta(days=today_dt.weekday())
    week_start = monday.strftime("%Y-%m-%d")
    weekly_rows = write_period_leaderboard(sheets, ws, config, "Weekly Leaderboard", week_start, today, learners=learners)

    # Monthly Leaderboard (1st of current month to today)
    month_start = today_dt.replace(day=1).strftime("%Y-%m-%d")
    monthly_rows = write_period_leaderboard(sheets, ws, config, "Monthly Leaderboard", month_start, today, learners=learners)

    # Custom Leaderboard (if configured)
    custom_start = config.get("custom_leaderboard_start", "").strip()
    custom_end = config.get("custom_leaderboard_end", "").strip()
    if custom_start and custom_end:
        write_period_leaderboard(sheets, ws, config, "Custom Leaderboard", custom_start, custom_end, learners=learners)

    write_daily_view(sheets, ws)

    write_summary(sheets, leaderboard_rows)

    write_alerts(sheets, leaderboard_rows, ws, config)

    write_external_sheet(sheets, leaderboard_rows, ws, config,
                         weekly_rows=weekly_rows, monthly_rows=monthly_rows)

    format_sheets(sheets)
    protect_sheets(sheets)

    print("\nDaily fetch complete.")


if __name__ == "__main__":
    main()
