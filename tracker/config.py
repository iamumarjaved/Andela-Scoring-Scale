"""Shared config loading for all scripts.

Reads environment variables for GitHub and Google Sheets credentials,
initializes API clients, loads the Config tab, and resolves learners
from the Roster tab by matching GitHub usernames to repository forks.
"""

import json
import os
import base64

from tracker.github_client import GitHubClient
from tracker.sheets_client import SheetsClient


def _parse_username_from_url(url):
    """Extract a GitHub username from a profile URL or plain username string.

    Args:
        url: A GitHub profile URL or bare username.

    Returns:
        The extracted username string.
    """
    return url.strip().rstrip("/").split("/")[-1]


def _load_learners_from_roster(sheets, gh, base_repos):
    """Read GitHub accounts from the Roster tab and resolve their forks.

    Tries the 'Roster' tab first, falling back to the legacy 'Metrics'
    tab for backwards compatibility. Column B (index 1) contains GitHub
    account URLs or usernames, starting from row 3.

    Args:
        sheets: SheetsClient instance.
        gh: GitHubClient instance.
        base_repos: List of "owner/repo" strings to search for forks.

    Returns:
        List of learner dicts with keys: username, fork_repo, base_repo.
    """
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
    usernames = []
    for row in rows[2:]:
        if len(row) >= 2 and row[1].strip():
            usernames.append(_parse_username_from_url(row[1]))

    if not usernames:
        return []

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
            learners.append({
                "username": username,
                "fork_repo": f"{username}/llm_engineering",
                "base_repo": base_repos[0],
            })

    return learners


def load_env():
    """Load credentials, initialize clients, and resolve learners.

    Reads GH_TRACKING_PAT, GOOGLE_SHEETS_CREDS, and GOOGLE_SHEET_ID
    from environment variables, builds a GitHubClient and SheetsClient,
    reads the Config tab for runtime settings, and resolves learners
    from the Roster tab.

    Returns:
        Tuple of (GitHubClient, SheetsClient, config dict, base_repos list,
        learners list).
    """
    token = os.environ["GH_TRACKING_PAT"]
    creds_b64 = os.environ["GOOGLE_SHEETS_CREDS"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]

    creds_json = json.loads(base64.b64decode(creds_b64))
    gh = GitHubClient(token)
    sheets = SheetsClient(creds_json, sheet_id)

    config = sheets.read_config()
    base_repos = [r.strip() for r in config.get("base_repos", "ed-donner/llm_engineering").split(",")]

    learners = _load_learners_from_roster(sheets, gh, base_repos)

    return gh, sheets, config, base_repos, learners
