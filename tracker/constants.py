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

CONFIG_DEFAULTS = [
    ("bootcamp_start_date", "2026-02-23"),
    ("inactive_threshold_days", "7"),
    ("at_risk_score_threshold", "30"),
    ("declining_score_threshold", "50"),
    ("declining_active_days_min", "2"),
    ("consistency_max_points", "30"),
    ("consistency_active_days_weight", "20"),
    ("consistency_commits_weight", "10"),
    ("collaboration_max_points", "25"),
    ("pr_points_each", "2"),
    ("review_points_each", "1.5"),
    ("issue_points_each", "1"),
    ("comment_points_each", "0.5"),
    ("collab_pr_cap", "8"),
    ("collab_review_cap", "7"),
    ("collab_issue_cap", "5"),
    ("collab_comment_cap", "5"),
    ("code_volume_max_points", "25"),
    ("lines_added_max_scale", "500"),
    ("lines_deleted_max_scale", "200"),
    ("code_volume_added_weight", "15"),
    ("code_volume_deleted_weight", "10"),
    ("quality_max_points", "20"),
    ("merge_rate_max_points", "15"),
    ("feedback_max_points", "5"),
    ("feedback_points_each", "1"),
    ("classify_excellent", "80"),
    ("classify_good", "60"),
    ("classify_average", "40"),
    ("classify_needs_improvement", "20"),
]
