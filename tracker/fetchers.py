"""GitHub data fetching for base repos and individual learners.

Provides bulk fetching of PRs/issues/comments from base repositories,
per-day metrics for a single learner, and all-time aggregated metrics
filtered by bootcamp start date.
"""

from datetime import datetime, timedelta, timezone


def fetch_base_repo_data(gh, base_repos, since=None, include_review_comments=False):
    """Fetch PRs, issues, and comments from base repos in bulk.

    Calls the GitHub API once per base repo to collect shared data that
    is then filtered per-learner downstream, avoiding redundant requests.

    Args:
        gh: GitHubClient instance.
        base_repos: List of "owner/repo" strings.
        since: Optional ISO timestamp to filter comments.
        include_review_comments: If True, also fetch PR review comments.

    Returns:
        Dict mapping repo full name to a dict with keys: prs, issues,
        comments, review_comments.
    """
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
    """Fetch all metrics for one learner on a single day.

    Collects commits, PRs, issues, comments, line stats, merge times,
    and rejection rates for the given date.

    Args:
        gh: GitHubClient instance.
        learner: Dict with username, fork_repo, base_repo keys.
        base_repo_data: Pre-fetched base repo data from fetch_base_repo_data.
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        Dict of daily metrics: commits, prs_opened, prs_merged,
        issues_opened, issue_comments, review_comments_given,
        lines_added, lines_deleted, avg_merge_time, rejection_rate.
    """
    username = learner["username"]
    fork_owner, fork_repo = learner["fork_repo"].split("/")
    since = f"{date_str}T00:00:00Z"
    until = f"{date_str}T23:59:59Z"

    try:
        commits = gh.get_commits(fork_owner, fork_repo, since=since, until=until)
        commits = [c for c in commits if c.get("author") and c["author"].get("login", "").lower() == username.lower()]
    except Exception:
        commits = []

    total_added = 0
    total_deleted = 0
    for commit in commits:
        try:
            stats = gh.get_commit_stats(fork_owner, fork_repo, commit["sha"])
            total_added += stats["additions"]
            total_deleted += stats["deletions"]
        except Exception:
            pass

    data = base_repo_data.get(learner["base_repo"], {"prs": [], "issues": [], "comments": []})
    user_prs = [p for p in data["prs"] if p["user"]["login"].lower() == username.lower()]

    prs_opened = len([p for p in user_prs if p["created_at"][:10] == date_str])
    merged_prs = [p for p in user_prs if p.get("merged_at") and p["merged_at"][:10] == date_str]
    prs_merged = len(merged_prs)

    merge_times = []
    for pr in merged_prs:
        created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
        merged = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
        merge_times.append((merged - created).total_seconds() / 3600)
    avg_merge_time = round(sum(merge_times) / len(merge_times), 1) if merge_times else 0

    closed_prs = [p for p in user_prs if p["state"] == "closed" and p.get("closed_at", "")[:10] == date_str]
    rejected = [p for p in closed_prs if not p.get("merged_at")]
    rejection_rate = round(len(rejected) / len(closed_prs), 2) if closed_prs else 0

    user_issues = [i for i in data["issues"] if i["user"]["login"].lower() == username.lower()]
    issues_opened = len([i for i in user_issues if i["created_at"][:10] == date_str])

    issue_comments = len([
        c for c in data["comments"]
        if c["user"]["login"].lower() == username.lower() and c["created_at"][:10] == date_str
    ])

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
    """Fetch all-time aggregated metrics for one learner.

    Collects total commits, active days, PR stats, line counts,
    comments received/given, merge times, rejection rates, and
    the most recent comment on the learner's PRs. All data is
    filtered to only include activity on or after bootcamp_start_date.

    Args:
        gh: GitHubClient instance.
        learner: Dict with username, fork_repo, base_repo keys.
        base_repo_data: Pre-fetched base repo data from fetch_base_repo_data.
        config: Optional config dict for bootcamp_start_date.

    Returns:
        Dict of all-time metrics: total_commits, weekly_commits,
        active_days, lines_added, lines_deleted, prs_opened, prs_merged,
        comments_received, comments_given, issues_opened, avg_merge_time,
        rejection_rate, last_active, last_comment.
    """
    username = learner["username"]
    fork_owner, fork_repo = learner["fork_repo"].split("/")
    base_owner, base_repo = learner["base_repo"].split("/")

    bootcamp_start_str = (config or {}).get("bootcamp_start_date", "2026-02-23")
    try:
        bootcamp_start = datetime.strptime(bootcamp_start_str, "%Y-%m-%d").date()
    except ValueError:
        bootcamp_start = datetime(2026, 2, 23).date()
    bootcamp_start_iso = f"{bootcamp_start.isoformat()}T00:00:00Z"

    try:
        all_commits = gh.get_commits(fork_owner, fork_repo, author=username, since=bootcamp_start_iso)
    except Exception:
        all_commits = []

    total_commits = len(all_commits)

    active_dates = set()
    for c in all_commits:
        d = c["commit"]["author"]["date"][:10]
        if d >= bootcamp_start_str:
            active_dates.add(d)

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
    try:
        weekly_commits = gh.get_commits(fork_owner, fork_repo, since=week_ago, author=username)
    except Exception:
        weekly_commits = []
    weekly_commit_count = len(weekly_commits)

    data = base_repo_data.get(learner["base_repo"], {
        "prs": [], "issues": [], "comments": [], "review_comments": [],
    })
    user_prs = [
        p for p in data["prs"]
        if p["user"]["login"].lower() == username.lower()
        and p["created_at"][:10] >= bootcamp_start_str
    ]

    prs_opened = len(user_prs)
    prs_merged = len([p for p in user_prs if p.get("merged_at")])

    pr_active_dates = set()
    for pr in user_prs:
        pr_active_dates.add(pr["created_at"][:10])

    total_added = 0
    total_deleted = 0
    pr_lines = {}
    for pr in user_prs:
        try:
            pr_detail = gh.get_pr_detail(base_owner, base_repo, pr["number"])
            additions = pr_detail.get("additions", 0)
            deletions = pr_detail.get("deletions", 0)
            total_added += additions
            total_deleted += deletions
            pr_lines[pr["number"]] = {
                "date": pr["created_at"][:10],
                "additions": additions,
                "deletions": deletions,
            }
        except Exception:
            pass

    for pr in user_prs:
        d = pr["created_at"][:10]
        if d >= bootcamp_start_str:
            active_dates.add(d)
    active_days = len(active_dates)

    merge_times = []
    for pr in user_prs:
        if pr.get("merged_at"):
            created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
            merged = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
            merge_times.append((merged - created).total_seconds() / 3600)
    avg_merge_time = round(sum(merge_times) / len(merge_times), 1) if merge_times else 0

    closed_prs = [p for p in user_prs if p["state"] == "closed"]
    rejected = [p for p in closed_prs if not p.get("merged_at")]
    rejection_rate = round(len(rejected) / len(closed_prs), 2) if closed_prs else 0

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
        if c["created_at"] > last_comment_date:
            last_comment_date = c["created_at"]
            last_comment_text = c.get("body", "")

    if len(last_comment_text) > 200:
        last_comment_text = last_comment_text[:200] + "..."

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

    user_issues = [
        i for i in data["issues"]
        if i["user"]["login"].lower() == username.lower()
        and i["created_at"][:10] >= bootcamp_start_str
    ]
    issues_opened = len(user_issues)

    last_active = max(active_dates) if active_dates else "N/A"

    return {
        "total_commits": total_commits,
        "weekly_commits": weekly_commit_count,
        "active_days": active_days,
        "pr_active_days": len(pr_active_dates),
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
        # Raw date-tagged data for period filtering (no extra API calls)
        "_commit_dates": [c["commit"]["author"]["date"][:10] for c in all_commits
                          if c["commit"]["author"]["date"][:10] >= bootcamp_start_str],
        "_user_prs": user_prs,
        "_user_issues": user_issues,
        "_comments_given_dates": (
            [c["created_at"][:10] for c in all_issue_comments
             if c["user"]["login"].lower() == username.lower()
             and c["created_at"][:10] >= bootcamp_start_str]
            + [c["created_at"][:10] for c in all_review_comments
               if c["user"]["login"].lower() == username.lower()
               and c["created_at"][:10] >= bootcamp_start_str]
        ),
        "_pr_lines": pr_lines,
    }


def compute_period_metrics(alltime_metrics, start_date, end_date):
    """Filter all-time raw data to a date range and return period metrics.

    Uses the _commit_dates, _user_prs, _user_issues, _comments_given_dates,
    and _pr_lines fields from fetch_learner_alltime to compute period-specific
    metrics without any extra API calls.

    Args:
        alltime_metrics: Dict returned by fetch_learner_alltime (with _ fields).
        start_date: Start date string (YYYY-MM-DD), inclusive.
        end_date: End date string (YYYY-MM-DD), inclusive.

    Returns:
        Dict of period metrics compatible with compute_scores.
    """
    commit_dates = [d for d in alltime_metrics.get("_commit_dates", [])
                    if start_date <= d <= end_date]

    user_prs = alltime_metrics.get("_user_prs", [])
    # PRs created in the period
    period_prs_created = [p for p in user_prs if start_date <= p["created_at"][:10] <= end_date]
    # PRs merged in the period (even if created earlier — reflects ongoing work)
    period_prs_merged = [p for p in user_prs
                         if p.get("merged_at") and start_date <= p["merged_at"][:10] <= end_date]
    # PRs active in the period: created OR merged during this window
    period_pr_numbers = {p["number"] for p in period_prs_created} | {p["number"] for p in period_prs_merged}
    period_prs = [p for p in user_prs if p["number"] in period_pr_numbers]

    user_issues = alltime_metrics.get("_user_issues", [])
    period_issues = [i for i in user_issues if start_date <= i["created_at"][:10] <= end_date]

    comment_dates = [d for d in alltime_metrics.get("_comments_given_dates", [])
                     if start_date <= d <= end_date]

    # Lines from PRs created OR merged during the period
    pr_lines = alltime_metrics.get("_pr_lines", {})
    lines_added = sum(v["additions"] for num, v in pr_lines.items() if num in period_pr_numbers)
    lines_deleted = sum(v["deletions"] for num, v in pr_lines.items() if num in period_pr_numbers)

    active_dates = set(commit_dates)
    for p in period_prs_created:
        active_dates.add(p["created_at"][:10])
    for p in period_prs_merged:
        active_dates.add(p["merged_at"][:10])
    for i in period_issues:
        active_dates.add(i["created_at"][:10])
    active_dates.update(comment_dates)

    pr_active_dates = set()
    for p in period_prs_created:
        pr_active_dates.add(p["created_at"][:10])
    for p in period_prs_merged:
        pr_active_dates.add(p["merged_at"][:10])

    merge_times = []
    for pr in period_prs_merged:
        created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
        merged = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
        merge_times.append((merged - created).total_seconds() / 3600)
    avg_merge_time = round(sum(merge_times) / len(merge_times), 1) if merge_times else 0

    prs_opened = len(period_prs_created)
    prs_merged = len(period_prs_merged)
    rejection_rate = (1 - (prs_merged / prs_opened)) if prs_opened > 0 else 0

    return {
        "active_days": len(active_dates),
        "pr_active_days": len(pr_active_dates),
        "total_commits": len(commit_dates),
        "weekly_commits": len(commit_dates),
        "prs_opened": prs_opened,
        "prs_merged": prs_merged,
        "issues_opened": len(period_issues),
        "comments_given": len(comment_dates),
        "comments_received": 0,
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
        "avg_merge_time": avg_merge_time,
        "rejection_rate": rejection_rate,
        "last_active": max(active_dates) if active_dates else "",
        "last_comment": "",
    }
