#!/usr/bin/env python3
"""One-time backfill of Daily Raw Metrics with historical data.

Efficiently fetches all commits, PRs, issues, and comments since
bootcamp_start for every learner, groups by date, and writes daily
rows to the Daily Raw Metrics tab. Skips dates that already exist.

After running, period leaderboards (Weekly, Monthly) will be accurate.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tracker.config import load_env
from tracker.constants import DAILY_HEADERS
from tracker.fetchers import fetch_base_repo_data
from tracker.writers import sort_daily_raw_metrics


def main():
    gh, sheets, config, base_repos, learners = load_env()

    bootcamp_start = config.get("bootcamp_start_date", "2026-02-23")
    bootcamp_iso = f"{bootcamp_start}T00:00:00Z"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Backfilling {len(learners)} learners from {bootcamp_start} to {today}")

    # Ensure headers
    ws = sheets.get_worksheet("Daily Raw Metrics")
    existing = ws.row_values(1) if ws.row_count > 0 else []
    if not existing or existing[0] != "Username":
        ws.update(values=[DAILY_HEADERS], range_name="A1")

    # Load existing rows to skip duplicates
    all_existing = ws.get_all_values()
    existing_keys = set()
    for row in all_existing[1:]:
        if len(row) >= 2:
            existing_keys.add((row[0].lower(), row[1]))
    print(f"  {len(existing_keys)} existing daily rows, will skip duplicates")

    # Fetch base repo data once (PRs, issues, comments, review comments)
    base_repo_data = fetch_base_repo_data(
        gh, base_repos, since=bootcamp_iso, include_review_comments=True
    )

    all_rows = []
    for idx, learner in enumerate(learners, 1):
        username = learner["username"]
        fork_owner, fork_repo = learner["fork_repo"].split("/")
        base_owner, base_repo_name = learner["base_repo"].split("/")

        print(f"  [{idx}/{len(learners)}] {username}...", end="", flush=True)

        # Fetch all commits at once (one API call per learner)
        try:
            all_commits = gh.get_commits(
                fork_owner, fork_repo, since=bootcamp_iso, author=username
            )
        except Exception:
            all_commits = []

        # Group commits by date
        commits_by_date = {}
        for c in all_commits:
            d = c["commit"]["author"]["date"][:10]
            if d >= bootcamp_start:
                commits_by_date.setdefault(d, []).append(c)

        # Get user's PRs and issues from base repo data
        repo_data = base_repo_data.get(
            learner["base_repo"],
            {"prs": [], "issues": [], "comments": [], "review_comments": []},
        )
        user_prs = [
            p for p in repo_data["prs"]
            if p["user"]["login"].lower() == username.lower()
            and p["created_at"][:10] >= bootcamp_start
        ]
        user_issues = [
            i for i in repo_data["issues"]
            if i["user"]["login"].lower() == username.lower()
            and i["created_at"][:10] >= bootcamp_start
        ]
        all_comments = repo_data.get("comments", [])
        all_review_comments = repo_data.get("review_comments", [])

        # Fetch PR line stats once per PR, group by creation date
        pr_lines_by_date = {}
        for pr in user_prs:
            d = pr["created_at"][:10]
            try:
                detail = gh.get_pr_detail(base_owner, base_repo_name, pr["number"])
                pr_lines_by_date.setdefault(d, [0, 0])
                pr_lines_by_date[d][0] += detail.get("additions", 0)
                pr_lines_by_date[d][1] += detail.get("deletions", 0)
            except Exception:
                pass

        # Collect all dates with any activity
        active_dates = set(commits_by_date.keys())
        for p in user_prs:
            active_dates.add(p["created_at"][:10])
            if p.get("merged_at"):
                active_dates.add(p["merged_at"][:10])
        for i in user_issues:
            active_dates.add(i["created_at"][:10])
        for c in all_comments:
            if c["user"]["login"].lower() == username.lower() and c["created_at"][:10] >= bootcamp_start:
                active_dates.add(c["created_at"][:10])
        for c in all_review_comments:
            if c["user"]["login"].lower() == username.lower() and c["created_at"][:10] >= bootcamp_start:
                active_dates.add(c["created_at"][:10])

        learner_count = 0
        for date_str in sorted(active_dates):
            if date_str < bootcamp_start or date_str > today:
                continue
            if (username.lower(), date_str) in existing_keys:
                continue

            commits = commits_by_date.get(date_str, [])
            prs_opened = len([p for p in user_prs if p["created_at"][:10] == date_str])
            merged_prs = [p for p in user_prs if p.get("merged_at") and p["merged_at"][:10] == date_str]
            prs_merged = len(merged_prs)

            issues_opened = len([i for i in user_issues if i["created_at"][:10] == date_str])

            issue_comments = len([
                c for c in all_comments
                if c["user"]["login"].lower() == username.lower()
                and c["created_at"][:10] == date_str
            ])
            review_comments = len([
                c for c in all_review_comments
                if c["user"]["login"].lower() == username.lower()
                and c["created_at"][:10] == date_str
            ])

            lines = pr_lines_by_date.get(date_str, [0, 0])

            merge_times = []
            for pr in merged_prs:
                created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                merged = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
                merge_times.append((merged - created).total_seconds() / 3600)
            avg_mt = round(sum(merge_times) / len(merge_times), 1) if merge_times else 0

            closed_prs = [
                p for p in user_prs
                if p["state"] == "closed" and p.get("closed_at", "")[:10] == date_str
            ]
            rejected = [p for p in closed_prs if not p.get("merged_at")]
            rej_rate = round(len(rejected) / len(closed_prs), 2) if closed_prs else 0

            has_activity = any([
                len(commits), prs_opened, prs_merged, issues_opened,
                issue_comments, review_comments, lines[0], lines[1],
            ])
            if has_activity:
                all_rows.append([
                    username, date_str, len(commits), prs_opened, prs_merged,
                    issues_opened, issue_comments, review_comments,
                    lines[0], lines[1], avg_mt, rej_rate, now,
                ])
                learner_count += 1

        print(f" {learner_count} days")

    print(f"\nWriting {len(all_rows)} backfill rows...")
    if all_rows:
        next_row = len(all_existing) + 1
        needed_rows = next_row + len(all_rows)
        if ws.row_count < needed_rows:
            ws.add_rows(needed_rows - ws.row_count)
            print(f"  Expanded sheet to {needed_rows} rows")
        updates = []
        for i, row_data in enumerate(all_rows):
            r = next_row + i
            updates.append({"range": f"A{r}:M{r}", "values": [row_data]})

        chunk_size = 200
        for i in range(0, len(updates), chunk_size):
            ws.batch_update(updates[i:i + chunk_size])
            print(f"  Written {min(i + chunk_size, len(updates))}/{len(updates)}")

    sort_daily_raw_metrics(ws)
    print(f"\nBackfill complete. {len(all_rows)} new rows added.")


if __name__ == "__main__":
    main()
