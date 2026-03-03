"""Score computation for learner metrics.

Calculates Consistency, Collaboration, Code Volume, and Quality scores
from all-time metrics using config-driven weights, caps, and thresholds.

Consistency: Daily PR activity ratio (pr_active_days / total_days).
Collaboration: PRs opened + code reviews given.
Code Volume: Lines of code added.
Quality: PR merge rate.
"""

from datetime import datetime, timezone


def compute_scores(metrics, config, end_date=None):
    """Compute four component scores, total score, and classification.

    All scoring parameters (weights, caps, scales, thresholds) are read
    from the config dict so admins can tune them via the Config sheet tab.

    Args:
        metrics: Dict of learner metrics from fetch_learner_alltime or
            aggregated daily data.
        config: Dict of config key-value pairs from the Config sheet.
        end_date: Optional date object. When provided, total_days is computed
            as end_date - bootcamp_start instead of today - bootcamp_start.

    Returns:
        Dict with keys: consistency, collaboration, code_volume, quality,
        total_score, classification.
    """
    m = metrics

    consistency_max = float(config.get("consistency_max_points", 30))
    collaboration_max = float(config.get("collaboration_max_points", 25))
    code_volume_max = float(config.get("code_volume_max_points", 25))
    quality_max = float(config.get("quality_max_points", 20))

    pr_pts = float(config.get("pr_points_each", 2))
    review_pts = float(config.get("review_points_each", 1.5))
    collab_pr_cap = float(config.get("collab_pr_cap", 15))
    collab_review_cap = float(config.get("collab_review_cap", 10))

    lines_added_scale = float(config.get("lines_added_max_scale", 500))

    quality_max_points = float(config.get("quality_max_points", 20))

    classify_excellent = float(config.get("classify_excellent", 80))
    classify_good = float(config.get("classify_good", 60))
    classify_average = float(config.get("classify_average", 40))
    classify_needs_improvement = float(config.get("classify_needs_improvement", 20))

    # --- Consistency: daily PR activity ratio ---
    bootcamp_start_str = config.get("bootcamp_start_date", "2026-02-23")
    try:
        bootcamp_start = datetime.strptime(bootcamp_start_str, "%Y-%m-%d").date()
    except ValueError:
        bootcamp_start = datetime(2026, 2, 23).date()
    if end_date:
        total_days = max((end_date - bootcamp_start).days, 1)
    else:
        total_days = max((datetime.now(timezone.utc).date() - bootcamp_start).days, 1)

    pr_active_days = m.get("pr_active_days", 0)
    pr_active_ratio = min(1.0, pr_active_days / total_days)
    consistency = min(consistency_max, round(pr_active_ratio * consistency_max, 1))

    # --- Collaboration: PRs opened + code reviews given ---
    collab_prs = min(collab_pr_cap, m["prs_opened"] * pr_pts)
    collab_reviews = min(collab_review_cap, m["comments_given"] * review_pts)
    collaboration = min(collaboration_max, round(collab_prs + collab_reviews, 1))

    # --- Code Volume: lines added only ---
    added_score = min(code_volume_max, m["lines_added"] / lines_added_scale * code_volume_max)
    code_volume = min(code_volume_max, round(added_score, 1))

    # --- Quality: merge rate only ---
    merge_rate = (m["prs_merged"] / m["prs_opened"]) if m["prs_opened"] > 0 else 0
    quality = min(quality_max, round(merge_rate * quality_max_points, 1))

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
