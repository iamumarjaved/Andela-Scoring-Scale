# Andela Scoring — AI Engineering Bootcamp Tracker

Automated GitHub activity tracking and scoring system for ~200 AI Engineering Bootcamp learners. Monitors commits, pull requests, code reviews, issues, and comments across learner repositories, computes performance scores, and writes results to a shared Google Sheets dashboard.

## How It Works

```
GitHub API  ──>  Automated Pipeline (GitHub Actions)  ──>  Google Sheets Dashboard
```

The system runs two automated pipelines:

- **Poll Activity** — Runs every 30 minutes. Captures lightweight commit/PR/issue counts for real-time visibility.
- **Daily Deep Fetch** — Runs once daily at midnight UTC. Performs full analysis: per-commit line stats, merge times, rejection rates, scoring, classification, and alerts.

All activity is filtered to the bootcamp period (configurable start date, default: Feb 23, 2026). Only post-bootcamp contributions are counted toward scores.

## Google Sheets Dashboard

| Tab | Purpose |
|-----|---------|
| **Roster** | Enrolled learners (email + GitHub username) |
| **Leaderboard** | Ranked scores, classifications, all-time metrics, and latest PR feedback |
| **Daily View** | Per-day activity breakdown with Activity Scores (last 14 days) |
| **Alerts** | Flagged learners: INACTIVE, AT RISK, DECLINING |
| **Daily Raw Metrics** | Granular daily data per learner |
| **Config** | All scoring parameters and thresholds (admin-editable) |

## Scoring System (100 Points)

All scoring weights, caps, and thresholds are fully configurable from the **Config** tab in the spreadsheet. Changes take effect on the next scheduled run — no code changes needed.

| Component | Default Max | What It Measures |
|-----------|-------------|------------------|
| **Consistency** | 30 | How regularly the learner contributes (active day ratio + commit frequency) |
| **Collaboration** | 25 | Community engagement (PRs opened, review comments, issues, discussions) |
| **Code Volume** | 25 | Amount of code contributed (lines added + deleted across PRs) |
| **Quality** | 20 | Code acceptance rate (PR merge rate + feedback received from reviewers) |

### Classification

| Score Range | Classification |
|-------------|----------------|
| 80+ | EXCELLENT |
| 60 - 79 | GOOD |
| 40 - 59 | AVERAGE |
| 20 - 39 | NEEDS IMPROVEMENT |
| Below 20 | AT RISK |

All thresholds are configurable in the Config tab.

### Alerts

| Alert Type | Trigger |
|------------|---------|
| **INACTIVE** | No activity in 7+ days (configurable) |
| **AT RISK** | Total score below 30 (configurable) |
| **DECLINING** | Score below 50 with fewer than 2 active days in the last week (configurable) |

For detailed scoring formulas, column definitions, and all configuration keys, see [`sheets_formulas.md`](sheets_formulas.md).

## Setup

### 1. GitHub Personal Access Token

Create a [fine-grained PAT](https://github.com/settings/tokens?type=beta) with:
- **Repository access**: Public repositories (read-only)
- **Permissions**: Contents (read), Issues (read), Pull requests (read)

### 2. Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use existing)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Create a **Service Account** and download the JSON key
5. Base64-encode it: `base64 -i service_account.json | tr -d '\n'`

### 3. Google Sheet

1. Create a new Google Sheet
2. Share it with the service account email (Editor access)
3. Copy the Sheet ID from the URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`
4. The system auto-creates all required tabs, headers, formatting, and default config values on first run

### 4. GitHub Repository Secrets

Add these as repository secrets (`Settings > Secrets and variables > Actions`):

| Secret | Value |
|--------|-------|
| `GH_TRACKING_PAT` | GitHub Personal Access Token |
| `GOOGLE_SHEETS_CREDS` | Base64-encoded service account JSON |
| `GOOGLE_SHEET_ID` | Google Sheet ID |

## GitHub Actions

Two workflows run automatically:

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| **Poll Activity** | Every 30 minutes | Lightweight commit/PR/issue counts |
| **Daily Deep Fetch** | Midnight UTC | Full scoring, classification, alerts, formatting |

Both support manual triggering via the **Actions** tab in GitHub.

## Multi-Repo Support

Track learners across multiple base repositories by editing the `base_repos` value in the Config tab (comma-separated):
```
ed-donner/llm_engineering, another-org/another-repo
```

Fork discovery runs across all listed repos automatically.

## Maintenance

- **PAT renewal**: GitHub PATs expire periodically. Regenerate and update the `GH_TRACKING_PAT` secret.
- **Threshold tuning**: Edit any value in the Config tab — no code changes needed. See [`sheets_formulas.md`](sheets_formulas.md) for the full list of configurable parameters.
- **Adding learners**: Learners are auto-discovered via forks. For non-fork learners, add to `manual_users` in the Config tab.
- **Excluding users**: Add usernames to `excluded_users` in the Config tab (e.g., the repo owner).

## Project Structure

```
scripts/
  daily_fetch.py     # Daily deep fetch: scoring, leaderboard, alerts, formatting
  poll.py            # 30-min lightweight activity poll
  backfill.py        # One-time historical data backfill
tracker/
  config.py          # Environment + config loading
  github_client.py   # GitHub API wrapper
  sheets_client.py   # Google Sheets API wrapper
.github/workflows/
  daily-deep-fetch.yml
  poll-activity.yml
```
