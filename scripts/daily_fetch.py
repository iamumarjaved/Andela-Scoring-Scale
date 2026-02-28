#!/usr/bin/env python3
"""Daily deep fetch — per-commit stats, PR merge times, rejection rates.
Writes daily data to Daily Raw Metrics AND aggregated totals to Metrics tab."""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tracker.config import load_env

DAILY_HEADERS = [
    "Username", "Date", "Commits", "PRs Opened", "PRs Merged",
    "Issues Opened", "Issue Comments", "PR Review Comments Given",
    "Lines Added", "Lines Deleted", "PR Avg Merge Time (hrs)",
    "PR Rejection Rate", "Last Updated",
]


def fetch_base_repo_data(gh, base_repos, since=None):
    """Fetch PRs, issues, comments from base repos once."""
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
    return base_repo_data


def fetch_learner_day(gh, learner, base_repo_data, date_str):
    """Fetch all metrics for one learner for one day. Returns a dict of metrics."""
    username = learner["username"]
    fork_owner, fork_repo = learner["fork_repo"].split("/")
    since = f"{date_str}T00:00:00Z"
    until = f"{date_str}T23:59:59Z"

    # Commits on fork
    try:
        commits = gh.get_commits(fork_owner, fork_repo, since=since, until=until)
        commits = [c for c in commits if c.get("author") and c["author"].get("login", "").lower() == username.lower()]
    except Exception:
        commits = []

    # Per-commit line stats
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

    prs_opened = len([p for p in user_prs if p["created_at"][:10] == date_str])
    merged_prs = [p for p in user_prs if p.get("merged_at") and p["merged_at"][:10] == date_str]
    prs_merged = len(merged_prs)

    # Average merge time
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

    # PR review comments given
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

    return {
        "commits": len(commits),
        "prs_opened": prs_opened,
        "prs_merged": prs_merged,
        "issues_opened": issues_opened,
        "issue_comments": issue_comments,
        "review_comments_given": review_comments_given,
        "lines_added": total_added,
        "lines_deleted": total_deleted,
        "avg_merge_time": avg_merge_time,
        "rejection_rate": rejection_rate,
    }


def fetch_learner_alltime(gh, learner, base_repo_data):
    """Fetch all-time aggregated metrics for one learner for the Metrics tab."""
    username = learner["username"]
    fork_owner, fork_repo = learner["fork_repo"].split("/")
    base_owner, base_repo = learner["base_repo"].split("/")

    # All commits on fork
    try:
        all_commits = gh.get_commits(fork_owner, fork_repo, author=username)
    except Exception:
        all_commits = []

    total_commits = len(all_commits)

    # Count active days (unique dates with commits)
    active_dates = set()
    for c in all_commits:
        active_dates.add(c["commit"]["author"]["date"][:10])
    active_days = len(active_dates)

    # Weekly commits (last 7 days)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
    try:
        weekly_commits = gh.get_commits(fork_owner, fork_repo, since=week_ago, author=username)
    except Exception:
        weekly_commits = []
    weekly_commit_count = len(weekly_commits)

    # Per-commit line stats (sample last 50 commits to avoid rate limits)
    total_added = 0
    total_deleted = 0
    for commit in all_commits[:50]:
        try:
            stats = gh.get_commit_stats(fork_owner, fork_repo, commit["sha"])
            total_added += stats["additions"]
            total_deleted += stats["deletions"]
        except Exception:
            pass

    # All-time PR data from base repo
    data = base_repo_data.get(learner["base_repo"], {"prs": [], "issues": [], "comments": []})
    user_prs = [p for p in data["prs"] if p["user"]["login"].lower() == username.lower()]

    prs_opened = len(user_prs)
    prs_merged = len([p for p in user_prs if p.get("merged_at")])

    # Average merge time across all merged PRs
    merge_times = []
    for pr in user_prs:
        if pr.get("merged_at"):
            created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
            merged = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
            merge_times.append((merged - created).total_seconds() / 3600)
    avg_merge_time = round(sum(merge_times) / len(merge_times), 1) if merge_times else 0

    # Rejection rate (all time)
    closed_prs = [p for p in user_prs if p["state"] == "closed"]
    rejected = [p for p in closed_prs if not p.get("merged_at")]
    rejection_rate = round(len(rejected) / len(closed_prs), 2) if closed_prs else 0

    # PR review comments received (on this user's PRs)
    review_comments_received = 0
    for pr in user_prs[:20]:
        try:
            rc = gh.get_pr_review_comments(base_owner, base_repo, pr["number"])
            review_comments_received += len([c for c in rc if c["user"]["login"].lower() != username.lower()])
        except Exception:
            pass

    # PR review comments given (on other people's PRs) — check recent PRs
    review_comments_given = 0
    other_prs = [p for p in data["prs"] if p["user"]["login"].lower() != username.lower()]
    for pr in other_prs[:30]:
        try:
            rc = gh.get_pr_review_comments(base_owner, base_repo, pr["number"])
            review_comments_given += len([c for c in rc if c["user"]["login"].lower() == username.lower()])
        except Exception:
            pass

    # Repo contributions (PRs + issues + comments)
    user_issues = [i for i in data["issues"] if i["user"]["login"].lower() == username.lower()]
    user_comments = [c for c in data["comments"] if c["user"]["login"].lower() == username.lower()]
    repo_contributions = prs_opened + len(user_issues) + len(user_comments)

    return {
        "total_daily_commits": total_commits,
        "total_weekly_commits": weekly_commit_count,
        "active_days": active_days,
        "repo_contributions": repo_contributions,
        "lines_added": total_added,
        "lines_deleted": total_deleted,
        "prs_opened": prs_opened,
        "prs_merged": prs_merged,
        "review_comments_received": review_comments_received,
        "review_comments_given": review_comments_given,
        "avg_merge_time": avg_merge_time,
        "rejection_rate": rejection_rate,
    }


def fetch_day(gh, sheets, ws, learners, base_repos, date_str):
    """Fetch all metrics for a single day across all learners."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    since = f"{date_str}T00:00:00Z"

    base_repo_data = fetch_base_repo_data(gh, base_repos, since=since)

    all_row_data = []
    for learner in learners:
        m = fetch_learner_day(gh, learner, base_repo_data, date_str)

        all_row_data.append([
            learner["username"], date_str, m["commits"], m["prs_opened"], m["prs_merged"],
            m["issues_opened"], m["issue_comments"], m["review_comments_given"],
            m["lines_added"], m["lines_deleted"], m["avg_merge_time"], m["rejection_rate"], now,
        ])

        if m["commits"] > 0 or m["prs_opened"] > 0:
            print(f"  {learner['username']} ({date_str}): {m['commits']} commits, +{m['lines_added']}/-{m['lines_deleted']}, {m['prs_opened']} PRs")

    # Batch write to Daily Raw Metrics
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
        print(f"  Wrote {len(updates)} rows to Daily Raw Metrics")


def update_metrics_tab(gh, sheets, learners, base_repos):
    """Fetch all-time data and write to Metrics tab columns C-N."""
    print("\nUpdating Metrics tab with all-time data...")
    metrics_ws = sheets.spreadsheet.worksheet("Metrics")
    rows = metrics_ws.get_all_values()

    # Build username -> row index map (row 3 onwards, 0-indexed in rows = index 2)
    username_rows = {}
    for i, row in enumerate(rows[2:], start=3):  # data starts at row 3
        if len(row) >= 2 and row[1].strip():
            username = row[1].strip().rstrip("/").split("/")[-1]
            username_rows[username.lower()] = i

    base_repo_data = fetch_base_repo_data(gh, base_repos)

    updates = []
    for learner in learners:
        username = learner["username"]
        row_num = username_rows.get(username.lower())
        if not row_num:
            continue

        print(f"  Fetching all-time data for {username}...")
        m = fetch_learner_alltime(gh, learner, base_repo_data)

        # Metrics tab columns: C=Total Daily Commits, D=Total Weekly Commits,
        # E=Active Days, F=Repo Contributions, G=Lines Added, H=Lines Deleted,
        # I=PRs Opened, J=PRs Merged, K=PR Review Comments Received,
        # L=PR Review Comments Given, M=Average PR Merge Time, N=PR Rejection Rate
        updates.append({
            "range": f"C{row_num}:N{row_num}",
            "values": [[
                m["total_daily_commits"],
                m["total_weekly_commits"],
                m["active_days"],
                m["repo_contributions"],
                m["lines_added"],
                m["lines_deleted"],
                m["prs_opened"],
                m["prs_merged"],
                m["review_comments_received"],
                m["review_comments_given"],
                m["avg_merge_time"],
                m["rejection_rate"],
            ]],
        })

        print(f"    {username}: {m['total_daily_commits']} commits, {m['active_days']} active days, "
              f"{m['prs_opened']} PRs, +{m['lines_added']}/-{m['lines_deleted']} lines")

    if updates:
        metrics_ws.batch_update(updates)
        print(f"\n  Updated {len(updates)} rows in Metrics tab")


def main():
    gh, sheets, config, base_repos, learners = load_env()
    print(f"Daily deep fetch for {len(learners)} learners")

    # 1. Write today's daily data to Daily Raw Metrics
    ws = sheets.get_worksheet("Daily Raw Metrics")
    existing = ws.row_values(1) if ws.row_count > 0 else []
    if not existing or existing[0] != "Username":
        ws.update(values=[DAILY_HEADERS], range_name="A1")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fetch_day(gh, sheets, ws, learners, base_repos, today)

    # 2. Update Metrics tab with all-time aggregated data
    update_metrics_tab(gh, sheets, learners, base_repos)

    print("\nDaily fetch complete.")


if __name__ == "__main__":
    main()
