"""Shared config loading for all scripts."""

import json
import os
import base64

from tracker.github_client import GitHubClient
from tracker.sheets_client import SheetsClient
from tracker.fork_discovery import discover_learners


def load_env():
    """Load and return GitHubClient, SheetsClient, and parsed config."""
    token = os.environ["GH_TRACKING_PAT"]
    creds_b64 = os.environ["GOOGLE_SHEETS_CREDS"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]

    creds_json = json.loads(base64.b64decode(creds_b64))
    gh = GitHubClient(token)
    sheets = SheetsClient(creds_json, sheet_id)

    config = sheets.read_config()
    base_repos = [r.strip() for r in config.get("base_repos", "ed-donner/llm_engineering").split(",")]
    excluded = [u.strip() for u in config.get("excluded_users", "").split(",") if u.strip()]
    bootcamp_start = config.get("bootcamp_start_date", "")

    manual_users = []
    manual_raw = config.get("manual_users", "")
    if manual_raw:
        for entry in manual_raw.split(";"):
            parts = entry.strip().split(",")
            if len(parts) == 3:
                manual_users.append({
                    "username": parts[0].strip(),
                    "fork_repo": parts[1].strip(),
                    "base_repo": parts[2].strip(),
                })

    learners = discover_learners(gh, base_repos, excluded, manual_users, bootcamp_start)

    return gh, sheets, config, base_repos, learners
