"""Shared config loading for all scripts.

Reads environment variables for GitHub and Google Sheets credentials,
initializes API clients, loads the Config tab, and resolves learners.

When an external_sheet_id is configured, learners are read from the
external sheet's "General Metrics Data" tab (column B = GitHub accounts,
starting row 3). Otherwise falls back to the Roster tab.
"""

import json
import os
import base64

from tracker.constants import EXTERNAL_GROUP_TABS
from tracker.github_client import GitHubClient
from tracker.sheets_client import SheetsClient


def detect_group_columns(headers):
    """Detect email, name, and GitHub username column indices from headers.

    Handles various column layouts across group tabs by matching header
    text keywords. Prefers 'username' columns over 'link' columns.

    Args:
        headers: List of header strings from row 1 of a group tab.

    Returns:
        Tuple of (email_idx, name_idx, github_idx). Any may be None.
    """
    email_idx = name_idx = github_idx = github_link_idx = None
    for i, h in enumerate(headers):
        hl = h.lower().strip()
        if not hl:
            continue
        if "email" in hl:
            email_idx = i
        elif "username" in hl:
            github_idx = i
        elif "github" in hl:
            if "link" in hl:
                github_link_idx = i
            elif github_idx is None:
                github_idx = i
        elif "name" in hl:
            if name_idx is None:
                name_idx = i
    if github_idx is None:
        github_idx = github_link_idx
    return email_idx, name_idx, github_idx


def _parse_username_from_url(url):
    """Extract a GitHub username from a profile URL or plain username string.

    Args:
        url: A GitHub profile URL or bare username.

    Returns:
        The extracted username string.
    """
    return url.strip().rstrip("/").split("/")[-1]


def _resolve_forks(usernames, gh, base_repos):
    """Look up fork repos for a list of GitHub usernames.

    Args:
        usernames: List of GitHub username strings.
        gh: GitHubClient instance.
        base_repos: List of "owner/repo" strings to search for forks.

    Returns:
        List of learner dicts with keys: username, fork_repo, base_repo.
    """
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


def _load_learners_from_external(sheets, gh, base_repos, config):
    """Read GitHub accounts from group tabs in the external sheet.

    Iterates over all group tabs (Igniters, Euclid, etc.), auto-detects
    the GitHub column from headers, and parses usernames from URLs or
    plain text. Deduplicates across groups.

    Args:
        sheets: SheetsClient instance.
        gh: GitHubClient instance.
        base_repos: List of "owner/repo" strings to search for forks.
        config: Config dict (must contain external_sheet_id).

    Returns:
        List of learner dicts, or None if external sheet is not configured
        or cannot be read.
    """
    external_id = config.get("external_sheet_id", "").strip()
    if not external_id:
        return None

    try:
        ext_sp = sheets.gc.open_by_key(external_id)
    except Exception as e:
        print(f"  WARNING: Could not open external sheet: {e}")
        return None

    usernames = []
    for tab_name in EXTERNAL_GROUP_TABS:
        try:
            ws = ext_sp.worksheet(tab_name)
            rows = ws.get_all_values()
            if not rows:
                continue
            _, _, github_idx = detect_group_columns(rows[0])
            if github_idx is None:
                print(f"  WARNING: No GitHub column found in {tab_name}")
                continue
            for row in rows[1:]:
                if len(row) > github_idx and row[github_idx].strip():
                    username = _parse_username_from_url(row[github_idx])
                    if username:
                        usernames.append(username)
        except Exception as e:
            print(f"  WARNING: Could not read tab {tab_name}: {e}")

    if not usernames:
        return None

    seen = set()
    unique = []
    for u in usernames:
        if u.lower() not in seen:
            seen.add(u.lower())
            unique.append(u)

    print(f"  Loaded {len(unique)} learners from {len(EXTERNAL_GROUP_TABS)} group tabs")
    return _resolve_forks(unique, gh, base_repos)


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

    return _resolve_forks(usernames, gh, base_repos)


def load_env():
    """Load credentials, initialize clients, and resolve learners.

    Reads GH_TRACKING_PAT, GOOGLE_SHEETS_CREDS, and GOOGLE_SHEET_ID
    from environment variables, builds a GitHubClient and SheetsClient,
    reads the Config tab for runtime settings, and resolves learners.

    When external_sheet_id is configured, learners are loaded from the
    external sheet's General Metrics Data tab. Falls back to Roster tab.

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

    learners = _load_learners_from_external(sheets, gh, base_repos, config)
    if learners is None:
        learners = _load_learners_from_roster(sheets, gh, base_repos)

    return gh, sheets, config, base_repos, learners
