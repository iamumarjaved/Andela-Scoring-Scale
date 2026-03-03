# Scoring System & Sheet Reference

Complete reference for all Google Sheets tabs, column definitions, scoring formulas, and configuration options. All data is computed by the automated pipeline and written directly to the sheet — no manual formulas required.

---

## Tab Overview

| Tab | Purpose | Data Source |
|-----|---------|-------------|
| **Roster** | Learner enrollment list (email, GitHub username) | Manual / auto-discovered |
| **Leaderboard** | Ranked scores, classifications, and all-time metrics | `daily_fetch.py` |
| **Daily View** | Per-day per-learner activity with Activity Score (last 14 days) | `daily_fetch.py` |
| **Alerts** | Flagged learners: INACTIVE, AT RISK, DECLINING | `daily_fetch.py` |
| **Daily Raw Metrics** | Granular daily data per learner | `poll.py` + `daily_fetch.py` |
| **Config** | All scoring parameters, thresholds, and settings | Admin-editable |

All data is filtered to only include activity **after the bootcamp start date** (configured in Config tab, default: `2026-02-23`).

---

## Tab 1: Roster

| Col | Header | Description |
|-----|--------|-------------|
| A | Email | Learner's email address |
| B | GitHub Account | GitHub username (used for fork discovery) |

Learners are auto-discovered by scanning forks of the configured base repositories. Non-fork learners can be added via `manual_users` in the Config tab.

---

## Tab 2: Leaderboard

Ranked view of all learners with computed scores and all-time metrics.

| Col | Header | Description |
|-----|--------|-------------|
| A | Rank | Position by Total Score (descending) |
| B | Learner | GitHub username |
| C | Classification | EXCELLENT / GOOD / AVERAGE / NEEDS IMPROVEMENT / AT RISK |
| D | Total Score | Sum of all 4 component scores (max 100) |
| E | Consistency | Active day ratio + commit frequency (max configurable, default 30) |
| F | Collaboration | PRs + reviews + issues + comments (max configurable, default 25) |
| G | Code Volume | Lines added + deleted (max configurable, default 25) |
| H | Quality | PR merge rate + feedback received (max configurable, default 20) |
| I | Active Days | Number of unique days with activity since bootcamp start |
| J | Total Commits | Total commits on learner's fork since bootcamp start |
| K | PRs Opened | Pull requests opened on base repo since bootcamp start |
| L | PRs Merged | Pull requests merged on base repo since bootcamp start |
| M | Lines Added | Total lines added across all PRs |
| N | Lines Deleted | Total lines deleted across all PRs |
| O | Comments Received | Comments from others on learner's PRs (issue-style + inline review) |
| P | Comments Given | Comments by learner on any PR (issue-style + inline review) |
| Q | Avg Merge Time | Average time from PR creation to merge (formatted: min/hrs/days) |
| R | Rejection Rate | Percentage of closed PRs that were not merged |
| S | Last Active | Most recent date with any activity |
| T | Last Comment | Text of the most recent comment on learner's PRs (truncated to 200 chars) |

---

## Tab 3: Daily View

Per-day breakdown for the last 14 days, sorted by date (descending) then Activity Score (descending).

| Col | Header | Description |
|-----|--------|-------------|
| A | Date | Activity date (YYYY-MM-DD) |
| B | Learner | GitHub username |
| C | Commits | Commits on that day |
| D | PRs Opened | PRs opened on that day |
| E | PRs Merged | PRs merged on that day |
| F | Lines Added | Lines added on that day |
| G | Lines Deleted | Lines deleted on that day |
| H | Comments | Issue comments + PR review comments on that day |
| I | Activity Score | Daily activity score (0-10, see formula below) |

### Activity Score Formula (0-10)

```
Activity Score = min(10,
    min(3, commits * 1)
  + min(4, prs_opened * 2)
  + min(2, prs_merged * 1)
  + (1 if lines_added + lines_deleted > 0 else 0)
)
```

**Conditional formatting:**
- Score >= 8: Green
- Score 5-7: Yellow
- Score 3-4: Orange
- Score < 3: Red

---

## Tab 4: Alerts

Flagged learners who may need attention. Updated daily.

| Col | Header | Description |
|-----|--------|-------------|
| A | Learner | GitHub username |
| B | Alert Type | INACTIVE / AT RISK / DECLINING |
| C | Details | Human-readable explanation |
| D | Last Active | Most recent active date |
| E | Score | Current total score |

### Alert Conditions

| Alert | Trigger | Config Keys |
|-------|---------|-------------|
| **INACTIVE** | No activity in N+ days | `inactive_threshold_days` (default: 7) |
| **AT RISK** | Total score below threshold | `at_risk_score_threshold` (default: 30) |
| **DECLINING** | Score below threshold AND fewer than N active days in last 7 | `declining_score_threshold` (default: 50), `declining_active_days_min` (default: 2) |

**Conditional formatting:** INACTIVE = Red, AT RISK = Orange, DECLINING = Yellow.

---

## Tab 5: Daily Raw Metrics

Granular per-learner per-day data. Written by both `poll.py` (every 30 min) and `daily_fetch.py` (daily).

| Col | Header | Description |
|-----|--------|-------------|
| A | Username | GitHub username |
| B | Date | Activity date (YYYY-MM-DD) |
| C | Commits | Commits on fork that day |
| D | PRs Opened | PRs created on base repo that day |
| E | PRs Merged | PRs merged on base repo that day |
| F | Issues Opened | Issues created on base repo that day |
| G | Issue Comments | Issue comments by learner that day |
| H | PR Review Comments Given | Inline review comments by learner that day |
| I | Lines Added | Lines added across commits that day |
| J | Lines Deleted | Lines deleted across commits that day |
| K | PR Avg Merge Time (hrs) | Average merge time for PRs merged that day |
| L | PR Rejection Rate | Fraction of PRs closed-without-merge that day |
| M | Last Updated | Timestamp of last data write |

Sorted by Date descending, then Username ascending.

---

## Tab 6: Config

All scoring parameters, thresholds, and operational settings. **Admins can edit values directly in the sheet** — changes take effect on the next scheduled run.

### General Settings

| Key | Default | Description |
|-----|---------|-------------|
| `bootcamp_start_date` | `2026-02-23` | Only count activity after this date |
| `base_repos` | *(set in sheet)* | Comma-separated list of base repositories (owner/repo) |
| `excluded_users` | *(set in sheet)* | Comma-separated usernames to exclude from tracking |
| `manual_users` | *(empty)* | Non-fork learners: `user,fork,base;user2,fork2,base2` |

### Alert Thresholds

| Key | Default | Description |
|-----|---------|-------------|
| `inactive_threshold_days` | `7` | Days without activity to trigger INACTIVE alert |
| `at_risk_score_threshold` | `30` | Score below this triggers AT RISK alert |
| `declining_score_threshold` | `50` | Score below this (with low recent activity) triggers DECLINING |
| `declining_active_days_min` | `2` | Minimum active days in last 7 to avoid DECLINING flag |

### Consistency Scoring (default max: 30 points)

| Key | Default | Description |
|-----|---------|-------------|
| `consistency_max_points` | `30` | Maximum points for Consistency component |

Scores based on daily PR submission rate. Full marks for opening PRs every day; marks are proportionally reduced for gaps.

**Formula:**
```
pr_active_ratio = min(1.0, pr_active_days / days_since_bootcamp_start)

Consistency = min(consistency_max_points, pr_active_ratio * consistency_max_points)
```

### Collaboration Scoring (default max: 25 points)

| Key | Default | Description |
|-----|---------|-------------|
| `collaboration_max_points` | `25` | Maximum points for Collaboration component |
| `pr_points_each` | `2` | Points per PR opened |
| `review_points_each` | `1.5` | Points per code review comment given |
| `collab_pr_cap` | `15` | Max points from PRs |
| `collab_review_cap` | `10` | Max points from code reviews |

**Formula:**
```
collab_prs     = min(collab_pr_cap,     prs_opened * pr_points_each)
collab_reviews = min(collab_review_cap, comments_given * review_points_each)

Collaboration = min(collaboration_max_points, collab_prs + collab_reviews)
```

### Code Volume Scoring (default max: 25 points)

| Key | Default | Description |
|-----|---------|-------------|
| `code_volume_max_points` | `25` | Maximum points for Code Volume component |
| `lines_added_max_scale` | `500` | Lines added needed for max score |

**Formula:**
```
Code Volume = min(code_volume_max_points, lines_added / lines_added_max_scale * code_volume_max_points)
```

### Quality Scoring (default max: 20 points)

| Key | Default | Description |
|-----|---------|-------------|
| `quality_max_points` | `20` | Maximum points for Quality component |

Scores based purely on PR merge rate (accepted / opened).

**Formula:**
```
merge_rate = prs_merged / prs_opened  (0 if no PRs)

Quality = min(quality_max_points, merge_rate * quality_max_points)
```

### Classification Thresholds

| Key | Default | Description |
|-----|---------|-------------|
| `classify_excellent` | `80` | Score >= this = **EXCELLENT** |
| `classify_good` | `60` | Score >= this = **GOOD** |
| `classify_average` | `40` | Score >= this = **AVERAGE** |
| `classify_needs_improvement` | `20` | Score >= this = **NEEDS IMPROVEMENT** |
| *(below all thresholds)* | | **AT RISK** |

### Total Score

```
Total Score = Consistency + Collaboration + Code Volume + Quality  (max 100)
```

---

## Sheet Formatting

Applied automatically on every run:

- **All tabs**: Frozen header row, navy background with white bold text, auto-filters, auto-resized columns
- **Tab colors**: Roster (green), Leaderboard (gold), Weekly Leaderboard (light blue), Monthly Leaderboard (lime), Custom Leaderboard (amber), Daily View (blue), Alerts (red), Daily Raw Metrics (grey), Config (purple)
- **All Leaderboards**: Classification column color-coded (EXCELLENT=green, GOOD=blue, AVERAGE=yellow, NEEDS IMPROVEMENT=orange, AT RISK=red). Rank column bold + centered.
- **Daily View**: Activity Score column color-coded by value range
- **Alerts**: Alert Type column color-coded by severity
