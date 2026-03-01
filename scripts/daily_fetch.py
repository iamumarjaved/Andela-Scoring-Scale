#!/usr/bin/env python3
"""Daily deep fetch orchestrator.

Runs the full daily pipeline: sheet structure setup, config defaults,
daily metrics fetch, sorting, leaderboard update, daily view, alerts,
and formatting. All logic lives in tracker submodules.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tracker.config import load_env
from tracker.constants import DAILY_HEADERS
from tracker.formatting import setup_sheet_structure, ensure_config_defaults, format_sheets
from tracker.writers import (
    write_daily_metrics,
    sort_daily_raw_metrics,
    update_leaderboard,
    write_daily_view,
    write_alerts,
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
    write_daily_metrics(gh, sheets, ws, learners, base_repos, today)

    sort_daily_raw_metrics(ws)

    leaderboard_rows = update_leaderboard(gh, sheets, learners, base_repos, config)

    write_daily_view(sheets, ws)

    write_alerts(sheets, leaderboard_rows, ws, config)

    format_sheets(sheets)

    print("\nDaily fetch complete.")


if __name__ == "__main__":
    main()
