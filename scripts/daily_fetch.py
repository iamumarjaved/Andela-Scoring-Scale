#!/usr/bin/env python3
"""Daily deep fetch — per-commit stats, PR merge times, rejection rates."""

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


def fetch_day(gh, sheets, ws, learners, base_repos, date_str):
    """Fetch all metrics for a single day across all learners."""
    since = f"{date_str}T00:00:00Z"
    until = f"{date_str}T23:59:59Z"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch base-repo-level data ONCE
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
            comments = gh.get_issue_comments(base_owner, base_repo, since=since)
        except Exception:
            comments = []
        base_repo_data[repo_full] = {"prs": prs, "issues": issues, "comments": comments}

    # Collect all row data
    all_row_data = []

    for learner in learners:
        username = learner["username"]
        fork_owner, fork_repo = learner["fork_repo"].split("/")

        # Commits on fork
        try:
            commits = gh.get_commits(fork_owner, fork_repo, since=since, until=until)
            commits = [c for c in commits if c.get("author") and c["author"].get("login", "").lower() == username.lower()]
        except Exception:
            commits = []

        commit_count = len(commits)

        # Per-commit stats (lines added/deleted)
        total_added = 0
        total_deleted = 0
        for commit in commits:
            try:
                stats = gh.get_commit_stats(fork_owner, fork_repo, commit["sha"])
                total_added += stats["additions"]
                total_deleted += stats["deletions"]
            except Exception:
                pass

        # Filter base repo data for this learner
        data = base_repo_data.get(learner["base_repo"], {"prs": [], "issues": [], "comments": []})
        user_prs = [p for p in data["prs"] if p["user"]["login"].lower() == username.lower()]

        prs_today = [p for p in user_prs if p["created_at"][:10] == date_str]
        prs_opened = len(prs_today)

        merged_prs = [p for p in user_prs if p.get("merged_at") and p["merged_at"][:10] == date_str]
        prs_merged = len(merged_prs)

        # Average merge time (hours)
        merge_times = []
        for pr in merged_prs:
            created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
            merged = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
            merge_times.append((merged - created).total_seconds() / 3600)
        avg_merge_time = round(sum(merge_times) / len(merge_times), 1) if merge_times else 0

        # Rejection rate
        closed_prs = [p for p in user_prs if p["state"] == "closed" and p.get("closed_at", "")[:10] == date_str]
        rejected = [p for p in closed_prs if not p.get("merged_at")]
        rejection_rate = round(len(rejected) / len(closed_prs), 2) if closed_prs else 0

        # Issues
        user_issues = [i for i in data["issues"] if i["user"]["login"].lower() == username.lower()]
        issues_opened = len([i for i in user_issues if i["created_at"][:10] == date_str])

        # Issue comments
        issue_comments = len([
            c for c in data["comments"]
            if c["user"]["login"].lower() == username.lower() and c["created_at"][:10] == date_str
        ])

        # PR review comments given (check only this user's PRs to limit API calls)
        review_comments_given = 0
        base_owner, base_repo = learner["base_repo"].split("/")
        for pr in user_prs[:10]:
            try:
                rc = gh.get_pr_review_comments(base_owner, base_repo, pr["number"])
                review_comments_given += len([
                    c for c in rc
                    if c["user"]["login"].lower() == username.lower() and c["created_at"][:10] == date_str
                ])
            except Exception:
                pass

        all_row_data.append([
            username, date_str, commit_count, prs_opened, prs_merged,
            issues_opened, issue_comments, review_comments_given,
            total_added, total_deleted, avg_merge_time, rejection_rate, now,
        ])

        if commit_count > 0 or prs_opened > 0:
            print(f"  {username} ({date_str}): {commit_count} commits, +{total_added}/-{total_deleted}, {prs_opened} PRs")

    # Batch write all rows at once
    if all_row_data:
        existing_data = ws.get_all_values()
        existing_map = {}
        for i, row in enumerate(existing_data[1:], start=2):
            if len(row) >= 2:
                existing_map[(row[0].lower(), row[1])] = i

        updates = []
        next_row = len(existing_data) + 1
        for row_data in all_row_data:
            key = (row_data[0].lower(), row_data[1])
            if key in existing_map:
                r = existing_map[key]
            else:
                r = next_row
                next_row += 1
            updates.append({"range": f"A{r}:M{r}", "values": [row_data]})

        ws.batch_update(updates)
        print(f"  Wrote {len(updates)} rows to sheet")


def main():
    gh, sheets, config, base_repos, learners = load_env()
    print(f"Daily deep fetch for {len(learners)} learners")

    ws = sheets.get_worksheet("Daily Raw Metrics")
    existing = ws.row_values(1) if ws.row_count > 0 else []
    if not existing or existing[0] != "Username":
        ws.update(values=[HEADERS], range_name="A1")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fetch_day(gh, sheets, ws, learners, base_repos, today)
    print("Daily fetch complete.")


if __name__ == "__main__":
    main()
