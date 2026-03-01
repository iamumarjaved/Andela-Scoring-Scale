"""Score computation for learner metrics.

Calculates Consistency, Collaboration, Code Volume, and Quality scores
from all-time metrics using config-driven weights, caps, and thresholds.
"""

from datetime import datetime, timezone


def compute_scores(metrics, config):
    """Compute four component scores, total score, and classification.

    All scoring parameters (weights, caps, scales, thresholds) are read
    from the config dict so admins can tune them via the Config sheet tab.

    Args:
        metrics: Dict of all-time learner metrics from fetch_learner_alltime.
        config: Dict of config key-value pairs from the Config sheet.

    Returns:
        Dict with keys: consistency, collaboration, code_volume, quality,
        total_score, classification.
    """
    m = metrics

    consistency_max = float(config.get("consistency_max_points", 30))
    collaboration_max = float(config.get("collaboration_max_points", 25))
    code_volume_max = float(config.get("code_volume_max_points", 25))
    quality_max = float(config.get("quality_max_points", 20))

    active_days_weight = float(config.get("consistency_active_days_weight", 20))
    commits_per_day_weight = float(config.get("consistency_commits_weight", 10))

    pr_pts = float(config.get("pr_points_each", 2))
    review_pts = float(config.get("review_points_each", 1.5))
    issue_pts = float(config.get("issue_points_each", 1))
    comment_pts = float(config.get("comment_points_each", 0.5))
    collab_pr_cap = float(config.get("collab_pr_cap", 8))
    collab_review_cap = float(config.get("collab_review_cap", 7))
    collab_issue_cap = float(config.get("collab_issue_cap", 5))
    collab_comment_cap = float(config.get("collab_comment_cap", 5))

    lines_added_scale = float(config.get("lines_added_max_scale", 500))
    lines_deleted_scale = float(config.get("lines_deleted_max_scale", 200))
    code_volume_added_weight = float(config.get("code_volume_added_weight", 15))
    code_volume_deleted_weight = float(config.get("code_volume_deleted_weight", 10))

    merge_rate_max = float(config.get("merge_rate_max_points", 15))
    feedback_max = float(config.get("feedback_max_points", 5))
    feedback_pts_each = float(config.get("feedback_points_each", 1))

    classify_excellent = float(config.get("classify_excellent", 80))
    classify_good = float(config.get("classify_good", 60))
    classify_average = float(config.get("classify_average", 40))
    classify_needs_improvement = float(config.get("classify_needs_improvement", 20))

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

    collab_prs = min(collab_pr_cap, m["prs_opened"] * pr_pts)
    collab_reviews = min(collab_review_cap, m["comments_given"] * review_pts)
    collab_issues = min(collab_issue_cap, m["issues_opened"] * issue_pts)
    collab_comments = min(collab_comment_cap, (m["comments_given"] + m["comments_received"]) * comment_pts)
    collaboration = min(collaboration_max, round(collab_prs + collab_reviews + collab_issues + collab_comments, 1))

    added_score = min(code_volume_added_weight, m["lines_added"] / lines_added_scale * code_volume_added_weight)
    deleted_score = min(code_volume_deleted_weight, m["lines_deleted"] / lines_deleted_scale * code_volume_deleted_weight)
    code_volume = min(code_volume_max, round(added_score + deleted_score, 1))

    merge_rate = (m["prs_merged"] / m["prs_opened"]) if m["prs_opened"] > 0 else 0
    quality_merge = min(merge_rate_max, merge_rate * merge_rate_max)
    quality_feedback = min(feedback_max, m["comments_received"] * feedback_pts_each)
    quality = min(quality_max, round(quality_merge + quality_feedback, 1))

    total_score = round(consistency + collaboration + code_volume + quality, 1)

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
