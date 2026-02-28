#!/usr/bin/env python3
"""30-minute lightweight poll — fetches commit counts, PRs, issues, comments."""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tracker.config import load_env

HEADERS = [
    "Username", "Date", "Commits", "PRs Opened", "PRs Merged",
    "Issues Opened", "Issue Comments", "PR Review Comments Given",
    "Lines Added", "Lines Deleted", "PR Avg Merge Time (hrs)",
    "PR Rejection Rate", "Last Updated",
]


def main():
    gh, sheets, config, base_repos, learners = load_env()

    last_poll = config.get("last_poll_timestamp", "")
    if not last_poll:
        last_poll = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

    print(f"Tracking {len(learners)} learners across {len(base_repos)} repos")

    ws = sheets.get_worksheet("Daily Raw Metrics")
    existing = ws.row_values(1) if ws.row_count > 0 else []
    if not existing or existing[0] != "Username":
        ws.update(values=[HEADERS], range_name="A1")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch base-repo-level data once
    base_repo_data = {}
    for repo_full in base_repos:
        base_owner, base_repo = repo_full.split("/")
        print(f"  Fetching base repo data: {repo_full}...")
        try:
            prs = gh.get_pull_requests(base_owner, base_repo, state="all")
        except Exception:
            prs = []
        try:
            issues = gh.get_issues(base_owner, base_repo)
        except Exception:
            issues = []
        try:
            comments = gh.get_issue_comments(base_owner, base_repo, since=last_poll)
        except Exception:
            comments = []
        base_repo_data[repo_full] = {"prs": prs, "issues": issues, "comments": comments}

    # Collect all rows
    all_rows = []
    for learner in learners:
        username = learner["username"]
        fork_owner, fork_repo = learner["fork_repo"].split("/")

        try:
            commits = gh.get_commits(fork_owner, fork_repo, since=last_poll)
            commits = [c for c in commits if c.get("author") and c["author"].get("login", "").lower() == username.lower()]
        except Exception:
            commits = []

        commit_count = len(commits)

        data = base_repo_data.get(learner["base_repo"], {"prs": [], "issues": [], "comments": []})
        user_prs = [p for p in data["prs"] if p["user"]["login"].lower() == username.lower()]
        prs_opened = len([p for p in user_prs if p["created_at"] >= last_poll])
        prs_merged = len([p for p in user_prs if p.get("merged_at") and p["merged_at"] >= last_poll])

        user_issues = [i for i in data["issues"] if i["user"]["login"].lower() == username.lower()]
        issues_opened = len([i for i in user_issues if i["created_at"] >= last_poll])

        issue_comments = len([c for c in data["comments"] if c["user"]["login"].lower() == username.lower()])

        all_rows.append([
            username, today, commit_count, prs_opened, prs_merged,
            issues_opened, issue_comments, 0,
            "", "", "", "", now,
        ])

        if commit_count > 0 or prs_opened > 0:
            print(f"  {username}: {commit_count} commits, {prs_opened} PRs, {issues_opened} issues")

    # Batch write
    if all_rows:
        existing_data = ws.get_all_values()
        existing_map = {}
        for i, row in enumerate(existing_data[1:], start=2):
            if len(row) >= 2:
                existing_map[(row[0].lower(), row[1])] = i

        updates = []
        next_row = len(existing_data) + 1
        for row_data in all_rows:
            key = (row_data[0].lower(), row_data[1])
            if key in existing_map:
                r = existing_map[key]
            else:
                r = next_row
                next_row += 1
            updates.append({"range": f"A{r}:M{r}", "values": [row_data]})

        ws.batch_update(updates)
        print(f"  Wrote {len(updates)} rows")

    # Sort Daily Raw Metrics: Date DESC, Username ASC
    print("  Sorting Daily Raw Metrics...")
    all_sorted = ws.get_all_values()
    if len(all_sorted) > 1:
        sort_headers = all_sorted[0]
        sort_rows = all_sorted[1:]
        sort_rows.sort(key=lambda r: r[0].lower() if r else "")
        sort_rows.sort(key=lambda r: r[1] if len(r) > 1 else "", reverse=True)
        sorted_data = [sort_headers] + sort_rows
        col = chr(64 + len(sort_headers)) if len(sort_headers) <= 26 else "Z"
        ws.update(values=sorted_data, range_name=f"A1:{col}{len(sorted_data)}")

    # Update last poll timestamp
    config_ws = sheets.get_worksheet("Config")
    all_config = config_ws.get_all_values()
    for i, row in enumerate(all_config):
        if row and row[0].strip() == "last_poll_timestamp":
            config_ws.update_cell(i + 1, 2, now)
            break

    print("Poll complete.")


if __name__ == "__main__":
    main()
