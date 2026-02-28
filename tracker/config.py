"""Shared config loading for all scripts."""

import json
import os
import base64

from tracker.github_client import GitHubClient
from tracker.sheets_client import SheetsClient


def _parse_username_from_url(url):
    """Extract GitHub username from a URL or plain username."""
    return url.strip().rstrip("/").split("/")[-1]


def _load_learners_from_roster(sheets, gh, base_repos):
    """Read GitHub accounts from the Roster tab and resolve their forks.
    Falls back to 'Metrics' tab for backwards compatibility during migration."""
    ws = None
    for tab_name in ("Roster", "Metrics"):
        try:
            ws = sheets.spreadsheet.worksheet(tab_name)
            break
        except Exception:
            continue
    if ws is None:
        return []

    rows = ws.get_all_values()
    # Column B (index 1) has GitHub accounts, starting from row 3 (row 1 is title, row 2 is headers)
    usernames = []
    for row in rows[2:]:
        if len(row) >= 2 and row[1].strip():
            usernames.append(_parse_username_from_url(row[1]))

    if not usernames:
        return []

    # Build fork map for each base repo
    fork_map = {}
    for repo_full in base_repos:
        owner, repo = repo_full.split("/")
        forks = gh.get_forks(owner, repo)
        for f in forks:
            fork_map[f["owner"]["login"].lower()] = {
                "full_name": f["full_name"],
                "base_repo": repo_full,
            }

    learners = []
    for username in usernames:
        fork_info = fork_map.get(username.lower())
        if fork_info:
            learners.append({
                "username": username,
                "fork_repo": fork_info["full_name"],
                "base_repo": fork_info["base_repo"],
            })
        else:
            # No fork found — still track PRs/issues on base repo
            learners.append({
                "username": username,
                "fork_repo": f"{username}/llm_engineering",
                "base_repo": base_repos[0],
            })

    return learners


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

    # Load learners from the Roster tab
    learners = _load_learners_from_roster(sheets, gh, base_repos)

    return gh, sheets, config, base_repos, learners
