#!/usr/bin/env python3
"""Daily deep fetch — per-commit stats, PR merge times, rejection rates.
Writes daily data to Daily Raw Metrics, Leaderboard, Daily View, and Alerts tabs."""

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

LEADERBOARD_HEADERS = [
    "Rank", "Learner", "Classification", "Total Score", "Consistency",
    "Collaboration", "Code Volume", "Quality", "Active Days",
    "Total Commits", "PRs Opened", "PRs Merged", "Lines Added",
    "Lines Deleted", "Comments Received", "Comments Given",
    "Avg Merge Time", "Rejection Rate", "Last Active", "Last Comment",
]

DAILY_VIEW_HEADERS = [
    "Date", "Learner", "Commits", "PRs Opened", "PRs Merged",
    "Lines Added", "Lines Deleted", "Comments", "Activity Score",
]

ALERTS_HEADERS = [
    "Learner", "Alert Type", "Details", "Last Active", "Score",
]


def fetch_base_repo_data(gh, base_repos, since=None, include_review_comments=False):
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
            comments = gh.get_issue_comments(base_owner, base_repo, since=since if since else None)
        except Exception:
            comments = []

        # Bulk fetch all PR review comments (avoids per-PR API calls)
        review_comments = []
        if include_review_comments:
            print(f"  Fetching all PR review comments for {repo_full}...")
            try:
                review_comments = gh.get_all_pr_review_comments(base_owner, base_repo, since=since)
            except Exception:
                review_comments = []
            print(f"    Got {len(review_comments)} review comments")

        base_repo_data[repo_full] = {
            "prs": prs, "issues": issues,
            "comments": comments, "review_comments": review_comments,
        }
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


def fetch_learner_alltime(gh, learner, base_repo_data, config=None):
    """Fetch all-time aggregated metrics for one learner (filtered by bootcamp start)."""
    username = learner["username"]
    fork_owner, fork_repo = learner["fork_repo"].split("/")
    base_owner, base_repo = learner["base_repo"].split("/")

    # Parse bootcamp start date for filtering
    bootcamp_start_str = (config or {}).get("bootcamp_start_date", "2026-02-23")
    try:
        bootcamp_start = datetime.strptime(bootcamp_start_str, "%Y-%m-%d").date()
    except ValueError:
        bootcamp_start = datetime(2026, 2, 23).date()
    bootcamp_start_iso = f"{bootcamp_start.isoformat()}T00:00:00Z"

    # All commits on fork (since bootcamp start)
    try:
        all_commits = gh.get_commits(fork_owner, fork_repo, author=username, since=bootcamp_start_iso)
    except Exception:
        all_commits = []

    total_commits = len(all_commits)

    # Count active days (unique dates with commits, only >= bootcamp_start)
    active_dates = set()
    for c in all_commits:
        d = c["commit"]["author"]["date"][:10]
        if d >= bootcamp_start_str:
            active_dates.add(d)

    # Weekly commits (last 7 days)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
    try:
        weekly_commits = gh.get_commits(fork_owner, fork_repo, since=week_ago, author=username)
    except Exception:
        weekly_commits = []
    weekly_commit_count = len(weekly_commits)

    # All-time PR data from base repo
    data = base_repo_data.get(learner["base_repo"], {
        "prs": [], "issues": [], "comments": [], "review_comments": [],
    })
    # Filter PRs created after bootcamp start
    user_prs = [
        p for p in data["prs"]
        if p["user"]["login"].lower() == username.lower()
        and p["created_at"][:10] >= bootcamp_start_str
    ]

    prs_opened = len(user_prs)
    prs_merged = len([p for p in user_prs if p.get("merged_at")])

    # Lines added/deleted — from PR details
    total_added = 0
    total_deleted = 0
    for pr in user_prs:
        try:
            pr_detail = gh.get_pr_detail(base_owner, base_repo, pr["number"])
            total_added += pr_detail.get("additions", 0)
            total_deleted += pr_detail.get("deletions", 0)
        except Exception:
            pass

    # Also count active days from PR creation dates
    for pr in user_prs:
        d = pr["created_at"][:10]
        if d >= bootcamp_start_str:
            active_dates.add(d)
    active_days = len(active_dates)

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

    # Comments received on this user's PRs (issue-style + inline review)
    # Also track last comment on learner's PRs for "Last Comment" column
    comments_received = 0
    last_comment_text = ""
    last_comment_date = ""

    for pr in user_prs:
        try:
            pr_comments = gh._request(
                f"{gh.BASE_URL}/repos/{base_owner}/{base_repo}/issues/{pr['number']}/comments"
            )
            for c in pr_comments:
                if c["created_at"][:10] < bootcamp_start_str:
                    continue
                if c["user"]["login"].lower() != username.lower():
                    comments_received += 1
                # Track latest comment from anyone on this learner's PRs
                if c["created_at"] > last_comment_date:
                    last_comment_date = c["created_at"]
                    last_comment_text = c.get("body", "")
        except Exception:
            pass

    all_review_comments = data.get("review_comments", [])
    user_pr_numbers = {pr["number"] for pr in user_prs}
    for c in all_review_comments:
        pr_url = c.get("pull_request_url", "")
        pr_num_str = pr_url.split("/")[-1]
        if not pr_num_str.isdigit():
            continue
        pr_num = int(pr_num_str)
        if pr_num not in user_pr_numbers:
            continue
        if c["created_at"][:10] < bootcamp_start_str:
            continue
        if c["user"]["login"].lower() != username.lower():
            comments_received += 1
        # Track latest review comment on this learner's PRs
        if c["created_at"] > last_comment_date:
            last_comment_date = c["created_at"]
            last_comment_text = c.get("body", "")

    # Truncate last comment to 200 chars
    if len(last_comment_text) > 200:
        last_comment_text = last_comment_text[:200] + "..."

    # Comments given by this user on ANY PR (filtered by bootcamp start)
    all_issue_comments = data.get("comments", [])
    comments_given = len([
        c for c in all_issue_comments
        if c["user"]["login"].lower() == username.lower()
        and c["created_at"][:10] >= bootcamp_start_str
    ])
    comments_given += len([
        c for c in all_review_comments
        if c["user"]["login"].lower() == username.lower()
        and c["created_at"][:10] >= bootcamp_start_str
    ])

    # Issues opened (filtered by bootcamp start)
    user_issues = [
        i for i in data["issues"]
        if i["user"]["login"].lower() == username.lower()
        and i["created_at"][:10] >= bootcamp_start_str
    ]
    issues_opened = len(user_issues)

    # Last active date
    last_active = max(active_dates) if active_dates else "N/A"

    return {
        "total_commits": total_commits,
        "weekly_commits": weekly_commit_count,
        "active_days": active_days,
        "lines_added": total_added,
        "lines_deleted": total_deleted,
        "prs_opened": prs_opened,
        "prs_merged": prs_merged,
        "comments_received": comments_received,
        "comments_given": comments_given,
        "issues_opened": issues_opened,
        "avg_merge_time": avg_merge_time,
        "rejection_rate": rejection_rate,
        "last_active": last_active,
        "last_comment": last_comment_text,
    }


def compute_scores(metrics, config):
    """Compute 4 component scores + total + classification from all-time metrics."""
    m = metrics

    # Read config values with defaults — ALL scoring params are config-driven
    consistency_max = float(config.get("consistency_max_points", 30))
    collaboration_max = float(config.get("collaboration_max_points", 25))
    code_volume_max = float(config.get("code_volume_max_points", 25))
    quality_max = float(config.get("quality_max_points", 20))

    # Consistency sub-weights
    active_days_weight = float(config.get("consistency_active_days_weight", 20))
    commits_per_day_weight = float(config.get("consistency_commits_weight", 10))

    # Collaboration per-item points and sub-caps
    pr_pts = float(config.get("pr_points_each", 2))
    review_pts = float(config.get("review_points_each", 1.5))
    issue_pts = float(config.get("issue_points_each", 1))
    comment_pts = float(config.get("comment_points_each", 0.5))
    collab_pr_cap = float(config.get("collab_pr_cap", 8))
    collab_review_cap = float(config.get("collab_review_cap", 7))
    collab_issue_cap = float(config.get("collab_issue_cap", 5))
    collab_comment_cap = float(config.get("collab_comment_cap", 5))

    # Code volume scales and sub-weights
    lines_added_scale = float(config.get("lines_added_max_scale", 500))
    lines_deleted_scale = float(config.get("lines_deleted_max_scale", 200))
    code_volume_added_weight = float(config.get("code_volume_added_weight", 15))
    code_volume_deleted_weight = float(config.get("code_volume_deleted_weight", 10))

    # Quality sub-weights
    merge_rate_max = float(config.get("merge_rate_max_points", 15))
    feedback_max = float(config.get("feedback_max_points", 5))
    feedback_pts_each = float(config.get("feedback_points_each", 1))

    # Classification thresholds
    classify_excellent = float(config.get("classify_excellent", 80))
    classify_good = float(config.get("classify_good", 60))
    classify_average = float(config.get("classify_average", 40))
    classify_needs_improvement = float(config.get("classify_needs_improvement", 20))

    # Consistency: active_day_ratio × weight + commits_per_day × weight (capped)
    active_days = m["active_days"]
    total_commits = m["total_commits"]
    bootcamp_start_str = config.get("bootcamp_start_date", "2026-02-23")
    try:
        bootcamp_start = datetime.strptime(bootcamp_start_str, "%Y-%m-%d").date()
    except ValueError:
        bootcamp_start = datetime(2026, 2, 23).date()
    total_days = max((datetime.now(timezone.utc).date() - bootcamp_start).days, 1)
    active_ratio = min(1.0, active_days / total_days)
    commits_per_day = total_commits / total_days
    consistency = min(consistency_max, round(
        active_ratio * active_days_weight
        + min(commits_per_day_weight, commits_per_day * commits_per_day_weight), 1))

    # Collaboration: PRs×pts + reviews×pts + issues×pts + comments×pts (each sub-capped)
    collab_prs = min(collab_pr_cap, m["prs_opened"] * pr_pts)
    collab_reviews = min(collab_review_cap, m["comments_given"] * review_pts)
    collab_issues = min(collab_issue_cap, m["issues_opened"] * issue_pts)
    collab_comments = min(collab_comment_cap, (m["comments_given"] + m["comments_received"]) * comment_pts)
    collaboration = min(collaboration_max, round(collab_prs + collab_reviews + collab_issues + collab_comments, 1))

    # Code Volume: lines_added/scale × weight + lines_deleted/scale × weight (each sub-capped)
    added_score = min(code_volume_added_weight, m["lines_added"] / lines_added_scale * code_volume_added_weight)
    deleted_score = min(code_volume_deleted_weight, m["lines_deleted"] / lines_deleted_scale * code_volume_deleted_weight)
    code_volume = min(code_volume_max, round(added_score + deleted_score, 1))

    # Quality: merge_rate × merge_rate_max + feedback × pts_each (capped)
    merge_rate = (m["prs_merged"] / m["prs_opened"]) if m["prs_opened"] > 0 else 0
    quality_merge = min(merge_rate_max, merge_rate * merge_rate_max)
    quality_feedback = min(feedback_max, m["comments_received"] * feedback_pts_each)
    quality = min(quality_max, round(quality_merge + quality_feedback, 1))

    total_score = round(consistency + collaboration + code_volume + quality, 1)

    # Classification (thresholds from config)
    if total_score >= classify_excellent:
        classification = "EXCELLENT"
    elif total_score >= classify_good:
        classification = "GOOD"
    elif total_score >= classify_average:
        classification = "AVERAGE"
    elif total_score >= classify_needs_improvement:
        classification = "NEEDS IMPROVEMENT"
    else:
        classification = "AT RISK"

    return {
        "consistency": consistency,
        "collaboration": collaboration,
        "code_volume": code_volume,
        "quality": quality,
        "total_score": total_score,
        "classification": classification,
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


def sort_daily_raw_metrics(ws):
    """Sort Daily Raw Metrics by Date DESC, then Username ASC."""
    print("\nSorting Daily Raw Metrics...")
    all_data = ws.get_all_values()
    if len(all_data) <= 1:
        return
    headers = all_data[0]
    rows = all_data[1:]

    # Two-pass stable sort: secondary key first (Username ASC), then primary (Date DESC)
    rows.sort(key=lambda r: r[0].lower() if r else "")
    rows.sort(key=lambda r: r[1] if len(r) > 1 else "", reverse=True)

    data = [headers] + rows
    col = chr(64 + len(headers)) if len(headers) <= 26 else "Z"
    ws.update(values=data, range_name=f"A1:{col}{len(data)}")
    print(f"  Sorted {len(rows)} rows")


def update_leaderboard(gh, sheets, learners, base_repos, config):
    """Fetch all-time data, compute scores, write to Leaderboard tab."""
    print("\nUpdating Leaderboard...")
    # Parse bootcamp start date for filtering
    bootcamp_start_str = config.get("bootcamp_start_date", "2026-02-23")
    try:
        bootcamp_start = datetime.strptime(bootcamp_start_str, "%Y-%m-%d").date()
    except ValueError:
        bootcamp_start = datetime(2026, 2, 23).date()
    bootcamp_start_iso = f"{bootcamp_start.isoformat()}T00:00:00Z"

    base_repo_data = fetch_base_repo_data(
        gh, base_repos, since=bootcamp_start_iso, include_review_comments=True
    )

    leaderboard_rows = []
    for learner in learners:
        username = learner["username"]
        print(f"  Fetching all-time data for {username}...")
        m = fetch_learner_alltime(gh, learner, base_repo_data, config=config)
        scores = compute_scores(m, config)

        # Format merge time
        mt = m["avg_merge_time"]
        if mt == 0:
            merge_time_str = "N/A"
        elif mt < 1:
            merge_time_str = f"{round(mt * 60)} min"
        elif mt < 24:
            merge_time_str = f"{round(mt, 1)} hrs"
        else:
            merge_time_str = f"{round(mt / 24, 1)} days"

        # Format rejection rate
        rejection_str = f"{round(m['rejection_rate'] * 100)}%"

        leaderboard_rows.append({
            "username": username,
            "classification": scores["classification"],
            "total_score": scores["total_score"],
            "consistency": scores["consistency"],
            "collaboration": scores["collaboration"],
            "code_volume": scores["code_volume"],
            "quality": scores["quality"],
            "active_days": m["active_days"],
            "total_commits": m["total_commits"],
            "prs_opened": m["prs_opened"],
            "prs_merged": m["prs_merged"],
            "lines_added": m["lines_added"],
            "lines_deleted": m["lines_deleted"],
            "comments_received": m["comments_received"],
            "comments_given": m["comments_given"],
            "avg_merge_time": merge_time_str,
            "rejection_rate": rejection_str,
            "last_active": m["last_active"],
            "last_comment": m.get("last_comment", ""),
        })

        print(f"    {username}: score={scores['total_score']}, {scores['classification']}")

    # Sort by total_score DESC
    leaderboard_rows.sort(key=lambda r: r["total_score"], reverse=True)

    # Build sheet rows with rank
    sheet_rows = []
    for rank, r in enumerate(leaderboard_rows, start=1):
        sheet_rows.append([
            rank, r["username"], r["classification"], r["total_score"],
            r["consistency"], r["collaboration"], r["code_volume"], r["quality"],
            r["active_days"], r["total_commits"], r["prs_opened"], r["prs_merged"],
            r["lines_added"], r["lines_deleted"], r["comments_received"],
            r["comments_given"], r["avg_merge_time"], r["rejection_rate"],
            r["last_active"], r["last_comment"],
        ])

    lb_ws = sheets.get_worksheet("Leaderboard")
    sheets.clear_and_write(lb_ws, LEADERBOARD_HEADERS, sheet_rows)
    print(f"  Wrote {len(sheet_rows)} rows to Leaderboard")

    return leaderboard_rows


def write_daily_view(sheets, raw_ws):
    """Read Daily Raw Metrics for last 14 days, compute Activity Score, write to Daily View."""
    print("\nWriting Daily View...")
    all_data = raw_ws.get_all_values()
    if len(all_data) <= 1:
        print("  No data in Daily Raw Metrics")
        return

    headers = all_data[0]
    rows = all_data[1:]

    # Get column indices from headers
    col_map = {h: i for i, h in enumerate(headers)}
    username_idx = col_map.get("Username", 0)
    date_idx = col_map.get("Date", 1)
    commits_idx = col_map.get("Commits", 2)
    prs_opened_idx = col_map.get("PRs Opened", 3)
    prs_merged_idx = col_map.get("PRs Merged", 4)
    lines_added_idx = col_map.get("Lines Added", 8)
    lines_deleted_idx = col_map.get("Lines Deleted", 9)
    issue_comments_idx = col_map.get("Issue Comments", 6)
    review_comments_idx = col_map.get("PR Review Comments Given", 7)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")

    # Collect all unique learners and dates in range
    learners_seen = set()
    dates_in_range = set()
    daily_data = {}  # (username, date) -> row data

    for row in rows:
        if len(row) <= date_idx:
            continue
        date_str = row[date_idx]
        username = row[username_idx]
        if date_str >= cutoff:
            learners_seen.add(username)
            dates_in_range.add(date_str)
            daily_data[(username, date_str)] = row

    def safe_int(val):
        try:
            return int(float(val)) if val else 0
        except (ValueError, TypeError):
            return 0

    # Build view rows — include 0-activity rows for all learners on all dates
    view_rows = []
    for date_str in sorted(dates_in_range, reverse=True):
        for username in sorted(learners_seen, key=str.lower):
            row = daily_data.get((username, date_str))
            if row:
                commits = safe_int(row[commits_idx] if len(row) > commits_idx else 0)
                prs_o = safe_int(row[prs_opened_idx] if len(row) > prs_opened_idx else 0)
                prs_m = safe_int(row[prs_merged_idx] if len(row) > prs_merged_idx else 0)
                lines_a = safe_int(row[lines_added_idx] if len(row) > lines_added_idx else 0)
                lines_d = safe_int(row[lines_deleted_idx] if len(row) > lines_deleted_idx else 0)
                comments = (
                    safe_int(row[issue_comments_idx] if len(row) > issue_comments_idx else 0)
                    + safe_int(row[review_comments_idx] if len(row) > review_comments_idx else 0)
                )
            else:
                commits = prs_o = prs_m = lines_a = lines_d = comments = 0

            # Activity Score: min(10, commits×1(max3) + prs_opened×2(max4) + prs_merged×1(max2) + 1 if lines>0)
            activity_score = min(10,
                min(3, commits * 1)
                + min(4, prs_o * 2)
                + min(2, prs_m * 1)
                + (1 if (lines_a + lines_d) > 0 else 0)
            )

            view_rows.append([
                date_str, username, commits, prs_o, prs_m,
                lines_a, lines_d, comments, activity_score,
            ])

    # Sort by Date DESC, then Activity Score DESC within each date
    # Two-pass stable sort: secondary key first, then primary
    view_rows.sort(key=lambda r: r[8], reverse=True)  # Activity Score DESC
    view_rows.sort(key=lambda r: r[0], reverse=True)   # Date DESC (stable, preserves score order)
    sorted_rows = view_rows

    dv_ws = sheets.get_worksheet("Daily View")
    sheets.clear_and_write(dv_ws, DAILY_VIEW_HEADERS, sorted_rows)
    print(f"  Wrote {len(sorted_rows)} rows to Daily View")


def write_alerts(sheets, leaderboard_rows, raw_ws, config):
    """Write flagged learners to Alerts tab."""
    print("\nWriting Alerts...")
    inactive_days = int(config.get("inactive_threshold_days", 7))
    at_risk_threshold = float(config.get("at_risk_score_threshold", 30))
    declining_threshold = float(config.get("declining_score_threshold", 50))
    declining_min_days = int(config.get("declining_active_days_min", 2))

    # Read Daily Raw Metrics for recent activity check
    all_data = raw_ws.get_all_values()
    headers = all_data[0] if all_data else []
    rows = all_data[1:] if len(all_data) > 1 else []

    col_map = {h: i for i, h in enumerate(headers)}
    username_idx = col_map.get("Username", 0)
    date_idx = col_map.get("Date", 1)
    # Activity columns: any non-zero value means the learner was active that day
    activity_cols = [
        col_map.get("Commits", 2),
        col_map.get("PRs Opened", 3),
        col_map.get("PRs Merged", 4),
        col_map.get("Issues Opened", 5),
        col_map.get("Issue Comments", 6),
        col_map.get("PR Review Comments Given", 7),
        col_map.get("Lines Added", 8),
        col_map.get("Lines Deleted", 9),
    ]

    today = datetime.now(timezone.utc).date()
    inactive_cutoff = (today - timedelta(days=inactive_days)).strftime("%Y-%m-%d")
    week_cutoff = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    # Build per-user recent activity
    user_last_active = {}  # username -> last active date string
    user_recent_active_days = {}  # username -> count of active days in last 7

    def safe_num(val):
        try:
            return float(val) if val else 0
        except (ValueError, TypeError):
            return 0

    for row in rows:
        if len(row) <= date_idx:
            continue
        username = row[username_idx]
        date_str = row[date_idx]

        # Check if ANY activity column is non-zero
        has_activity = any(safe_num(row[c]) > 0 for c in activity_cols if c < len(row))

        if has_activity:
            existing = user_last_active.get(username, "")
            if date_str > existing:
                user_last_active[username] = date_str

            if date_str >= week_cutoff:
                user_recent_active_days[username] = user_recent_active_days.get(username, 0) + 1

    alert_rows = []
    for entry in leaderboard_rows:
        username = entry["username"]
        score = entry["total_score"]
        # Use leaderboard's last_active as fallback (covers all-time data beyond raw metrics)
        last_active = user_last_active.get(username) or entry.get("last_active", "Never")

        alerts = []

        # INACTIVE: no activity in 7+ days
        if last_active == "Never" or last_active < inactive_cutoff:
            alerts.append(("INACTIVE", "No activity in 7+ days"))

        # AT RISK: score below threshold
        if score < at_risk_threshold:
            alerts.append(("AT RISK", f"Score {score} below {at_risk_threshold}"))

        # DECLINING: score < 50 and < 2 active days in last 7
        recent_days = user_recent_active_days.get(username, 0)
        if score < declining_threshold and recent_days < declining_min_days:
            # Don't double-flag if already INACTIVE
            if not any(a[0] == "INACTIVE" for a in alerts):
                alerts.append(("DECLINING", f"Score {score}, only {recent_days} active days this week"))

        for alert_type, details in alerts:
            alert_rows.append([
                username, alert_type, details, last_active, score,
            ])

    alerts_ws = sheets.get_worksheet("Alerts")
    sheets.clear_and_write(alerts_ws, ALERTS_HEADERS, alert_rows)
    print(f"  Wrote {len(alert_rows)} alerts")


def setup_sheet_structure(sheets):
    """Ensure sheet has the correct tab layout: Roster, Leaderboard, Daily View, Alerts, Daily Raw Metrics, Config."""
    print("Setting up sheet structure...")

    # Rename Metrics → Roster (if not already done)
    # Check if Roster already exists
    try:
        sheets.spreadsheet.worksheet("Roster")
        print("  Roster tab already exists")
    except Exception:
        # Try to rename Metrics → Roster
        try:
            metrics_ws = sheets.spreadsheet.worksheet("Metrics")
            metrics_ws.update_title("Roster")
            print("  Renamed 'Metrics' → 'Roster'")
            # Clear stats columns C-N (keep only A=email, B=GitHub account)
            rows = metrics_ws.get_all_values()
            if rows and len(rows[0]) > 2:
                last_col = chr(64 + len(rows[0])) if len(rows[0]) <= 26 else "Z"
                metrics_ws.batch_clear([f"C1:{last_col}{len(rows)}"])
                print("  Cleared columns C-N from Roster tab")
        except Exception:
            # Neither exists — create Roster
            sheets.get_worksheet("Roster")
            print("  Created new Roster tab")

    # Ensure all tabs exist (get_worksheet creates if missing)
    sheets.get_worksheet("Leaderboard")
    sheets.get_worksheet("Daily View")
    sheets.get_worksheet("Alerts")
    sheets.get_worksheet("Daily Raw Metrics")
    sheets.get_worksheet("Config")

    # Reorder tabs
    desired_order = ["Roster", "Leaderboard", "Daily View", "Alerts", "Daily Raw Metrics", "Config"]
    sheets.reorder_worksheets(desired_order)
    print("  Tabs reordered: " + " | ".join(desired_order))


def ensure_config_defaults(sheets):
    """Write missing config keys to Config tab so admins can see and edit them."""
    print("\nEnsuring config defaults...")
    defaults = [
        ("bootcamp_start_date", "2026-02-23"),
        ("inactive_threshold_days", "7"),
        ("at_risk_score_threshold", "30"),
        ("declining_score_threshold", "50"),
        ("declining_active_days_min", "2"),
        # Consistency scoring
        ("consistency_max_points", "30"),
        ("consistency_active_days_weight", "20"),
        ("consistency_commits_weight", "10"),
        # Collaboration scoring
        ("collaboration_max_points", "25"),
        ("pr_points_each", "2"),
        ("review_points_each", "1.5"),
        ("issue_points_each", "1"),
        ("comment_points_each", "0.5"),
        ("collab_pr_cap", "8"),
        ("collab_review_cap", "7"),
        ("collab_issue_cap", "5"),
        ("collab_comment_cap", "5"),
        # Code volume scoring
        ("code_volume_max_points", "25"),
        ("lines_added_max_scale", "500"),
        ("lines_deleted_max_scale", "200"),
        ("code_volume_added_weight", "15"),
        ("code_volume_deleted_weight", "10"),
        # Quality scoring
        ("quality_max_points", "20"),
        ("merge_rate_max_points", "15"),
        ("feedback_max_points", "5"),
        ("feedback_points_each", "1"),
        # Classification thresholds
        ("classify_excellent", "80"),
        ("classify_good", "60"),
        ("classify_average", "40"),
        ("classify_needs_improvement", "20"),
    ]

    ws = sheets.get_worksheet("Config")
    existing = ws.get_all_values()
    existing_keys = {row[0].strip() for row in existing if len(row) >= 1 and row[0].strip()}

    missing = [[key, value] for key, value in defaults if key not in existing_keys]

    if missing:
        next_row = len(existing) + 1
        updates = [
            {"range": f"A{next_row + i}:B{next_row + i}", "values": [row_data]}
            for i, row_data in enumerate(missing)
        ]
        ws.batch_update(updates)
        print(f"  Added {len(missing)} missing config keys")
    else:
        print("  All config keys present")


def format_sheets(sheets):
    """Apply formatting, colors, filters, and conditional formatting to all tabs."""
    print("\nFormatting sheets...")
    sp = sheets.spreadsheet

    def hex_to_rgb(hex_color):
        """Convert hex color to Google Sheets RGB dict (0-1 range)."""
        h = hex_color.lstrip("#")
        return {
            "red": int(h[0:2], 16) / 255,
            "green": int(h[2:4], 16) / 255,
            "blue": int(h[4:6], 16) / 255,
        }

    # --- Phase 1: Cleanup existing conditional formats and basic filters ---
    metadata = sp.fetch_sheet_metadata()
    cleanup_requests = []
    for sheet_data in metadata.get("sheets", []):
        sheet_id = sheet_data["properties"]["sheetId"]
        # Delete existing conditional format rules in reverse order
        cond_formats = sheet_data.get("conditionalFormats", [])
        for i in range(len(cond_formats) - 1, -1, -1):
            cleanup_requests.append({
                "deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}
            })
        # Clear existing basic filter
        if "basicFilter" in sheet_data:
            cleanup_requests.append({"clearBasicFilter": {"sheetId": sheet_id}})

    if cleanup_requests:
        sp.batch_update({"requests": cleanup_requests})

    # --- Phase 2: Build formatting requests ---
    tab_names = ["Roster", "Leaderboard", "Daily View", "Alerts", "Daily Raw Metrics", "Config"]
    tabs = {}
    for name in tab_names:
        try:
            tabs[name] = sp.worksheet(name)
        except Exception:
            pass

    tab_colors = {
        "Roster": "#70AD47",
        "Leaderboard": "#FFD700",
        "Daily View": "#4472C4",
        "Alerts": "#FF0000",
        "Daily Raw Metrics": "#808080",
        "Config": "#7030A0",
    }

    header_bg = hex_to_rgb("#1F3864")
    header_fg = {"red": 1, "green": 1, "blue": 1}
    requests = []

    # Common formatting for all tabs
    for tab_name, ws in tabs.items():
        num_cols = ws.col_count
        num_rows = ws.row_count

        # Tab color
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws.id,
                    "tabColorStyle": {"rgbColor": hex_to_rgb(tab_colors[tab_name])},
                },
                "fields": "tabColorStyle",
            }
        })

        # Freeze row 1
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws.id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        })

        # Bold white headers on dark navy background (row 1)
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": header_bg,
                        "textFormat": {"bold": True, "foregroundColor": header_fg},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        })

        # Auto-filter on data range
        requests.append({
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": 0,
                        "endRowIndex": num_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    }
                }
            }
        })

        # Auto-resize columns
        requests.append({
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": ws.id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": num_cols,
                }
            }
        })

    # --- Leaderboard: Classification col C (index 2) conditional formatting ---
    if "Leaderboard" in tabs:
        lb_ws = tabs["Leaderboard"]
        classification_colors = [
            ("EXCELLENT", "#C6EFCE"),
            ("GOOD", "#BDD7EE"),
            ("AVERAGE", "#FFF2CC"),
            ("NEEDS IMPROVEMENT", "#FCE4CC"),
            ("AT RISK", "#FFC7CE"),
        ]
        for idx, (text, color) in enumerate(classification_colors):
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": lb_ws.id,
                            "startRowIndex": 1, "endRowIndex": 1000,
                            "startColumnIndex": 2, "endColumnIndex": 3,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": text}],
                            },
                            "format": {"backgroundColor": hex_to_rgb(color)},
                        },
                    },
                    "index": idx,
                }
            })

        # Bold rank column A
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": lb_ws.id,
                    "startRowIndex": 1, "endRowIndex": 1000,
                    "startColumnIndex": 0, "endColumnIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
            }
        })

    # --- Daily View: Activity Score col I (index 8) conditional formatting ---
    if "Daily View" in tabs:
        dv_ws = tabs["Daily View"]
        dv_rules = [
            {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "8"}], "color": "#C6EFCE"},
            {"type": "NUMBER_BETWEEN", "values": [{"userEnteredValue": "5"}, {"userEnteredValue": "7"}], "color": "#FFF2CC"},
            {"type": "NUMBER_BETWEEN", "values": [{"userEnteredValue": "3"}, {"userEnteredValue": "4"}], "color": "#FCE4CC"},
            {"type": "NUMBER_LESS", "values": [{"userEnteredValue": "3"}], "color": "#FFC7CE"},
        ]
        for idx, rule in enumerate(dv_rules):
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": dv_ws.id,
                            "startRowIndex": 1, "endRowIndex": 1000,
                            "startColumnIndex": 8, "endColumnIndex": 9,
                        }],
                        "booleanRule": {
                            "condition": {"type": rule["type"], "values": rule["values"]},
                            "format": {"backgroundColor": hex_to_rgb(rule["color"])},
                        },
                    },
                    "index": idx,
                }
            })

    # --- Alerts: Alert Type col B (index 1) conditional formatting ---
    if "Alerts" in tabs:
        alerts_ws = tabs["Alerts"]
        alert_colors = [
            ("INACTIVE", "#FFC7CE"),
            ("AT RISK", "#FCE4CC"),
            ("DECLINING", "#FFF2CC"),
        ]
        for idx, (text, color) in enumerate(alert_colors):
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": alerts_ws.id,
                            "startRowIndex": 1, "endRowIndex": 1000,
                            "startColumnIndex": 1, "endColumnIndex": 2,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": text}],
                            },
                            "format": {"backgroundColor": hex_to_rgb(color)},
                        },
                    },
                    "index": idx,
                }
            })

    # Send all formatting requests in one batch
    if requests:
        sp.batch_update({"requests": requests})

    print("  Formatting applied to all tabs")


def main():
    gh, sheets, config, base_repos, learners = load_env()
    print(f"Daily deep fetch for {len(learners)} learners")

    # 0. Set up sheet structure (rename tabs, reorder)
    setup_sheet_structure(sheets)

    # 0b. Ensure all config defaults exist
    ensure_config_defaults(sheets)

    # 1. Write today's daily data to Daily Raw Metrics
    ws = sheets.get_worksheet("Daily Raw Metrics")
    existing = ws.row_values(1) if ws.row_count > 0 else []
    if not existing or existing[0] != "Username":
        ws.update(values=[DAILY_HEADERS], range_name="A1")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fetch_day(gh, sheets, ws, learners, base_repos, today)

    # 2. Sort Daily Raw Metrics
    sort_daily_raw_metrics(ws)

    # 3. Update Leaderboard with all-time scores
    leaderboard_rows = update_leaderboard(gh, sheets, learners, base_repos, config)

    # 4. Write Daily View (last 14 days)
    write_daily_view(sheets, ws)

    # 5. Write Alerts
    write_alerts(sheets, leaderboard_rows, ws, config)

    # 6. Apply formatting to all tabs
    format_sheets(sheets)

    print("\nDaily fetch complete.")


if __name__ == "__main__":
    main()
