"""Shared header definitions and configuration defaults for all tabs."""

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

SUMMARY_HEADERS = [
    "Rank", "Learner", "Classification", "Total Score",
    "Consistency", "Collaboration", "Code Volume", "Quality",
]

CONFIG_DEFAULTS = [
    ("bootcamp_start_date", "2026-02-23"),
    ("inactive_threshold_days", "7"),
    ("at_risk_score_threshold", "30"),
    ("declining_score_threshold", "50"),
    ("declining_active_days_min", "2"),
    ("consistency_max_points", "30"),
    ("collaboration_max_points", "25"),
    ("pr_points_each", "2"),
    ("review_points_each", "1.5"),
    ("collab_pr_cap", "15"),
    ("collab_review_cap", "10"),
    ("code_volume_max_points", "25"),
    ("lines_added_max_scale", "500"),
    ("quality_max_points", "20"),
    ("classify_excellent", "80"),
    ("classify_good", "60"),
    ("classify_average", "40"),
    ("classify_needs_improvement", "20"),
    ("custom_leaderboard_start", ""),
    ("custom_leaderboard_end", ""),
    ("external_sheet_id", ""),
]
