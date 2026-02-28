# Andela Scoring — GitHub Activity Tracker

Automated GitHub activity tracker for ~200 AI Engineering Bootcamp learners. Polls GitHub API on a schedule, writes raw metrics to Google Sheets, where formulas handle scoring, ranking, and alerts.

## Architecture

```
GitHub API  ──→  poll.py (every 30 min)  ──→  Google Sheets
                 daily_fetch.py (daily)  ──→  (formulas do scoring)
                 backfill.py (one-time)  ──→
```

**Scripts write raw data only.** All scoring, classification, trends, and alerts are handled by Google Sheets formulas (see `sheets_formulas.md`).

### Google Sheets Tabs

| Tab | Purpose |
|-----|---------|
| Daily Raw Metrics | Raw data written by scripts |
| Performance Summary | Scored rankings (formula-driven) |
| Weekly Snapshot | Week-over-week view (formula-driven) |
| Alerts | AT RISK / INACTIVE / DECLINING flags |
| Config | All configuration key-value pairs |

### Scoring Breakdown (100 points)

| Category | Points | What counts |
|----------|--------|-------------|
| Consistency | 30 | Active day ratio + commit frequency |
| Collaboration | 25 | PRs + reviews + issues + comments |
| Code Volume | 25 | Lines added + deleted |
| Quality | 20 | PR merge rate + feedback received |

## Setup

### 1. GitHub Personal Access Token

Create a [fine-grained PAT](https://github.com/settings/tokens?type=beta) with:
- **Repository access**: Public repositories (read-only)
- **Permissions**: Contents (read), Issues (read), Pull requests (read)

### 2. Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use existing)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Create a **Service Account** → download the JSON key
5. Base64-encode it: `base64 -i service_account.json | tr -d '\n'`

### 3. Google Sheet

1. Create a new Google Sheet
2. Share it with the service account email (Editor access)
3. Copy the Sheet ID from the URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`
4. Set up the **Config** tab with key-value pairs (see `sheets_formulas.md` Tab 5)
5. Set up formula tabs per `sheets_formulas.md`

### 4. GitHub Secrets

Add these as repository secrets (`Settings → Secrets → Actions`):

| Secret | Value |
|--------|-------|
| `GH_TRACKING_PAT` | Your GitHub PAT |
| `GOOGLE_SHEETS_CREDS` | Base64-encoded service account JSON |
| `GOOGLE_SHEET_ID` | The Sheet ID |

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GH_TRACKING_PAT="ghp_..."
export GOOGLE_SHEETS_CREDS="$(base64 -i service_account.json | tr -d '\n')"
export GOOGLE_SHEET_ID="your-sheet-id"

# Run 30-min poll
python scripts/poll.py

# Run daily deep fetch
python scripts/daily_fetch.py

# Backfill historical data
python scripts/backfill.py --start 2026-02-01

# Backfill specific range
python scripts/backfill.py --start 2026-02-01 --end 2026-02-15 --sleep 3
```

## GitHub Actions

Two workflows run automatically:

- **Poll Activity** (`poll-activity.yml`): Every 30 minutes — lightweight commit/PR/issue counts
- **Daily Deep Fetch** (`daily-deep-fetch.yml`): Midnight UTC — per-commit line stats, merge times, rejection rates

Both can be triggered manually via `workflow_dispatch` in the Actions tab.

## Multi-Repo Support

Edit the `base_repos` value in the Config tab (comma-separated):
```
ed-donner/llm_engineering, another-org/another-repo
```

Fork discovery runs across all listed repos.

## Maintenance

- **PAT renewal**: GitHub PATs expire. Regenerate and update the `GH_TRACKING_PAT` secret.
- **Rate limits**: The tracker uses ~200 learners × ~5 API calls = ~1000 calls per poll. GitHub allows 5000/hour with a PAT.
- **Threshold tuning**: Edit values in the Config tab — no code changes needed.
- **Adding learners**: They're auto-discovered via forks. For non-fork learners, add to `manual_users` in Config.
- **Excluding users**: Add usernames to `excluded_users` in Config (e.g., the repo owner).

## Cost

$0/month — GitHub Actions free tier (2000 min/month) and Google Sheets API (free).
