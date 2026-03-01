"""Sheet writing functions for Daily Raw Metrics, Leaderboard, Daily View, and Alerts.

Each function reads data, transforms it, and writes to the appropriate
Google Sheets tab via the SheetsClient.
"""

from datetime import datetime, timedelta, timezone

from tracker.constants import (
    DAILY_HEADERS,
    LEADERBOARD_HEADERS,
    DAILY_VIEW_HEADERS,
    ALERTS_HEADERS,
)
from tracker.fetchers import fetch_base_repo_data, fetch_learner_day, fetch_learner_alltime
from tracker.scoring import compute_scores


def write_daily_metrics(gh, sheets, ws, learners, base_repos, date_str):
    """Fetch metrics for a single day and write rows to Daily Raw Metrics.

    For each learner, fetches commit counts, PRs, issues, comments,
    line stats, merge times, and rejection rates, then batch-writes
    all rows to the worksheet (updating existing rows or appending new ones).

    Args:
        gh: GitHubClient instance.
        sheets: SheetsClient instance.
        ws: The Daily Raw Metrics worksheet object.
        learners: List of learner dicts with username, fork_repo, base_repo.
        base_repos: List of "owner/repo" strings.
        date_str: Date string in YYYY-MM-DD format.
    """
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
    """Sort Daily Raw Metrics by Date DESC, then Username ASC.

    Uses a two-pass stable sort: secondary key (Username ASC) first,
    then primary key (Date DESC).

    Args:
        ws: The Daily Raw Metrics worksheet object.
    """
    print("\nSorting Daily Raw Metrics...")
    all_data = ws.get_all_values()
    if len(all_data) <= 1:
        return
    headers = all_data[0]
    rows = all_data[1:]

    rows.sort(key=lambda r: r[0].lower() if r else "")
    rows.sort(key=lambda r: r[1] if len(r) > 1 else "", reverse=True)

    data = [headers] + rows
    col = chr(64 + len(headers)) if len(headers) <= 26 else "Z"
    ws.update(values=data, range_name=f"A1:{col}{len(data)}")
    print(f"  Sorted {len(rows)} rows")


def update_leaderboard(gh, sheets, learners, base_repos, config):
    """Fetch all-time data, compute scores, and write to the Leaderboard tab.

    For each learner, fetches all-time metrics (filtered by bootcamp start),
    computes scores using config-driven weights, ranks by total score, and
    writes the complete leaderboard with formatted merge times and rejection rates.

    Args:
        gh: GitHubClient instance.
        sheets: SheetsClient instance.
        learners: List of learner dicts.
        base_repos: List of "owner/repo" strings.
        config: Config dict from the Config sheet.

    Returns:
        List of leaderboard row dicts (used by write_alerts).
    """
    print("\nUpdating Leaderboard...")
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

        mt = m["avg_merge_time"]
        if mt == 0:
            merge_time_str = "N/A"
        elif mt < 1:
            merge_time_str = f"{round(mt * 60)} min"
        elif mt < 24:
            merge_time_str = f"{round(mt, 1)} hrs"
        else:
            merge_time_str = f"{round(mt / 24, 1)} days"

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

    leaderboard_rows.sort(key=lambda r: r["total_score"], reverse=True)

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
    """Build the Daily View tab from the last 14 days of Daily Raw Metrics.

    Reads raw metrics, computes an Activity Score for each learner-day
    combination (including zero-activity rows), and writes the sorted
    results to the Daily View tab.

    Args:
        sheets: SheetsClient instance.
        raw_ws: The Daily Raw Metrics worksheet object.
    """
    print("\nWriting Daily View...")
    all_data = raw_ws.get_all_values()
    if len(all_data) <= 1:
        print("  No data in Daily Raw Metrics")
        return

    headers = all_data[0]
    rows = all_data[1:]

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

    learners_seen = set()
    dates_in_range = set()
    daily_data = {}

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
        """Convert a value to int, returning 0 on failure."""
        try:
            return int(float(val)) if val else 0
        except (ValueError, TypeError):
            return 0

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

    view_rows.sort(key=lambda r: r[8], reverse=True)
    view_rows.sort(key=lambda r: r[0], reverse=True)

    dv_ws = sheets.get_worksheet("Daily View")
    sheets.clear_and_write(dv_ws, DAILY_VIEW_HEADERS, view_rows)
    print(f"  Wrote {len(view_rows)} rows to Daily View")


def write_alerts(sheets, leaderboard_rows, raw_ws, config):
    """Flag learners with inactivity, low scores, or declining trends.

    Reads Daily Raw Metrics for recent activity, cross-references
    with leaderboard scores, and writes alerts to the Alerts tab.

    Args:
        sheets: SheetsClient instance.
        leaderboard_rows: List of leaderboard row dicts from update_leaderboard.
        raw_ws: The Daily Raw Metrics worksheet object.
        config: Config dict from the Config sheet.
    """
    print("\nWriting Alerts...")
    inactive_days = int(config.get("inactive_threshold_days", 7))
    at_risk_threshold = float(config.get("at_risk_score_threshold", 30))
    declining_threshold = float(config.get("declining_score_threshold", 50))
    declining_min_days = int(config.get("declining_active_days_min", 2))

    all_data = raw_ws.get_all_values()
    headers = all_data[0] if all_data else []
    rows = all_data[1:] if len(all_data) > 1 else []

    col_map = {h: i for i, h in enumerate(headers)}
    username_idx = col_map.get("Username", 0)
    date_idx = col_map.get("Date", 1)
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

    user_last_active = {}
    user_recent_active_days = {}

    def safe_num(val):
        """Convert a value to float, returning 0 on failure."""
        try:
            return float(val) if val else 0
        except (ValueError, TypeError):
            return 0

    for row in rows:
        if len(row) <= date_idx:
            continue
        username = row[username_idx]
        date_str = row[date_idx]

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
        last_active = user_last_active.get(username) or entry.get("last_active", "Never")

        alerts = []

        if last_active in ("Never", "N/A") or last_active <= inactive_cutoff:
            alerts.append(("INACTIVE", f"No activity in {inactive_days}+ days"))

        if score < at_risk_threshold:
            alerts.append(("AT RISK", f"Score {score} below {at_risk_threshold}"))

        recent_days = user_recent_active_days.get(username, 0)
        if score < declining_threshold and recent_days < declining_min_days:
            if not any(a[0] == "INACTIVE" for a in alerts):
                day_word = "day" if recent_days == 1 else "days"
                alerts.append(("DECLINING", f"Score {score} (below {declining_threshold}), only {recent_days} active {day_word} in last 7 days"))

        for alert_type, details in alerts:
            alert_rows.append([
                username, alert_type, details, last_active, score,
            ])

    alerts_ws = sheets.get_worksheet("Alerts")
    sheets.clear_and_write(alerts_ws, ALERTS_HEADERS, alert_rows)
    print(f"  Wrote {len(alert_rows)} alerts")
