# Google Sheets Formulas Reference

Copy-paste-ready formulas for all tabs. The scripts write raw data to **Daily Raw Metrics**; everything else is formula-driven.

---

## Tab 1: Daily Raw Metrics

**Headers (Row 1):** Written automatically by the scripts.

| Col | Header |
|-----|--------|
| A | Username |
| B | Date |
| C | Commits |
| D | PRs Opened |
| E | PRs Merged |
| F | Issues Opened |
| G | Issue Comments |
| H | PR Review Comments Given |
| I | Lines Added |
| J | Lines Deleted |
| K | PR Avg Merge Time (hrs) |
| L | PR Rejection Rate |
| M | Last Updated |

No formulas needed — data is written by `poll.py` and `daily_fetch.py`.

---

## Tab 2: Performance Summary

**Headers (Row 1):**

| Col | Header |
|-----|--------|
| A | Username |
| B | Total Days |
| C | Active Days |
| D | Total Commits |
| E | Total PRs Opened |
| F | Total PRs Merged |
| G | Total Issues |
| H | Total Issue Comments |
| I | Total Review Comments Given |
| J | Total Lines Added |
| K | Total Lines Deleted |
| L | Avg Merge Time (hrs) |
| M | Avg Rejection Rate |
| N | Consistency Score (30) |
| O | Collaboration Score (25) |
| P | Code Volume Score (25) |
| Q | Quality Score (20) |
| R | Total Score (100) |
| S | Classification |
| T | Current Streak (days) |
| U | Last Active Date |

### Setup

1. Put unique usernames in column A starting from A2. Use this formula in A2 and drag down:
   ```
   =IFERROR(INDEX(SORT(UNIQUE('Daily Raw Metrics'!A2:A)), ROW()-1), "")
   ```

2. **Total Days (B2):**
   ```
   =IF(A2="","",COUNTUNIQUE(FILTER('Daily Raw Metrics'!B:B, 'Daily Raw Metrics'!A:A=A2)))
   ```

3. **Active Days (C2):** Days with at least 1 commit
   ```
   =IF(A2="","",COUNTIFS('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!C:C, ">"&0))
   ```

4. **Total Commits (D2):**
   ```
   =IF(A2="","",SUMIF('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!C:C))
   ```

5. **Total PRs Opened (E2):**
   ```
   =IF(A2="","",SUMIF('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!D:D))
   ```

6. **Total PRs Merged (F2):**
   ```
   =IF(A2="","",SUMIF('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!E:E))
   ```

7. **Total Issues (G2):**
   ```
   =IF(A2="","",SUMIF('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!F:F))
   ```

8. **Total Issue Comments (H2):**
   ```
   =IF(A2="","",SUMIF('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!G:G))
   ```

9. **Total Review Comments Given (I2):**
   ```
   =IF(A2="","",SUMIF('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!H:H))
   ```

10. **Total Lines Added (J2):**
    ```
    =IF(A2="","",SUMIF('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!I:I))
    ```

11. **Total Lines Deleted (K2):**
    ```
    =IF(A2="","",SUMIF('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!J:J))
    ```

12. **Avg Merge Time (L2):**
    ```
    =IF(A2="","",IFERROR(AVERAGEIFS('Daily Raw Metrics'!K:K, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!K:K, ">"&0), 0))
    ```

13. **Avg Rejection Rate (M2):**
    ```
    =IF(A2="","",IFERROR(AVERAGEIFS('Daily Raw Metrics'!L:L, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!L:L, ">"&0), 0))
    ```

### Scoring Formulas

14. **Consistency Score — 30 points (N2):**
    ```
    =IF(A2="","",MIN(30, ROUND((C2/MAX(B2,1))*20 + MIN(10, D2/MAX(B2,1)*10), 1)))
    ```
    - Active day ratio: up to 20 pts (active_days / total_days × 20)
    - Commit frequency: up to 10 pts (commits_per_day × 10, capped at 10)

15. **Collaboration Score — 25 points (O2):**
    ```
    =IF(A2="","",MIN(25, ROUND(MIN(8, E2*2) + MIN(7, I2*1.5) + MIN(5, G2) + MIN(5, H2*0.5), 1)))
    ```
    - PRs: up to 8 pts (2 per PR)
    - Reviews given: up to 7 pts (1.5 per review)
    - Issues: up to 5 pts (1 per issue)
    - Comments: up to 5 pts (0.5 per comment)

16. **Code Volume Score — 25 points (P2):**
    ```
    =IF(A2="","",MIN(25, ROUND(MIN(15, J2/500*15) + MIN(10, K2/200*10), 1)))
    ```
    - Lines added: up to 15 pts (linear scale, 500 lines = max)
    - Lines deleted: up to 10 pts (linear scale, 200 lines = max)

17. **Quality Score — 20 points (Q2):**
    ```
    =IF(A2="","",MIN(20, ROUND(IF(E2>0, (F2/E2)*15, 0) + MIN(5, I2*1), 1)))
    ```
    - Merge rate: up to 15 pts (merged / opened × 15)
    - Feedback received (review comments): up to 5 pts

18. **Total Score (R2):**
    ```
    =IF(A2="","",N2+O2+P2+Q2)
    ```

19. **Classification (S2):**
    ```
    =IF(A2="","",IF(R2>=80,"EXCELLENT",IF(R2>=60,"GOOD",IF(R2>=40,"AVERAGE",IF(R2>=20,"NEEDS IMPROVEMENT","AT RISK")))))
    ```

20. **Current Streak (T2):** (Approximate — counts consecutive recent active days)
    ```
    =IF(A2="","",COUNTIFS('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!C:C, ">"&0, 'Daily Raw Metrics'!B:B, ">="&TEXT(TODAY()-7,"YYYY-MM-DD")))
    ```

21. **Last Active Date (U2):**
    ```
    =IF(A2="","",MAXIFS('Daily Raw Metrics'!B:B, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!C:C, ">"&0))
    ```

---

## Tab 3: Weekly Snapshot

**Headers (Row 1):**

| Col | Header |
|-----|--------|
| A | Username |
| B | Week Start |
| C | Week End |
| D | Commits |
| E | PRs Opened |
| F | PRs Merged |
| G | Issues |
| H | Comments |
| I | Lines Added |
| J | Lines Deleted |

### Setup

Put usernames in column A and week start date in B2 (e.g., `2026-02-23`). Set C2:
```
=IF(B2="","",TEXT(DATEVALUE(B2)+6,"YYYY-MM-DD"))
```

### Formulas (Row 2, drag down)

1. **Weekly Commits (D2):**
   ```
   =IF(A2="","",SUMIFS('Daily Raw Metrics'!C:C, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!B:B, ">="&B2, 'Daily Raw Metrics'!B:B, "<="&C2))
   ```

2. **Weekly PRs Opened (E2):**
   ```
   =IF(A2="","",SUMIFS('Daily Raw Metrics'!D:D, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!B:B, ">="&B2, 'Daily Raw Metrics'!B:B, "<="&C2))
   ```

3. **Weekly PRs Merged (F2):**
   ```
   =IF(A2="","",SUMIFS('Daily Raw Metrics'!E:E, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!B:B, ">="&B2, 'Daily Raw Metrics'!B:B, "<="&C2))
   ```

4. **Weekly Issues (G2):**
   ```
   =IF(A2="","",SUMIFS('Daily Raw Metrics'!F:F, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!B:B, ">="&B2, 'Daily Raw Metrics'!B:B, "<="&C2))
   ```

5. **Weekly Comments (H2):**
   ```
   =IF(A2="","",SUMIFS('Daily Raw Metrics'!G:G, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!B:B, ">="&B2, 'Daily Raw Metrics'!B:B, "<="&C2))
   ```

6. **Weekly Lines Added (I2):**
   ```
   =IF(A2="","",SUMIFS('Daily Raw Metrics'!I:I, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!B:B, ">="&B2, 'Daily Raw Metrics'!B:B, "<="&C2))
   ```

7. **Weekly Lines Deleted (J2):**
   ```
   =IF(A2="","",SUMIFS('Daily Raw Metrics'!J:J, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!B:B, ">="&B2, 'Daily Raw Metrics'!B:B, "<="&C2))
   ```

---

## Tab 4: Alerts

**Headers (Row 1):**

| Col | Header |
|-----|--------|
| A | Username |
| B | Alert Type |
| C | Details |
| D | Last Active |
| E | Total Score |

### Setup

Link usernames from Performance Summary. Put in A2:
```
=IFERROR(INDEX('Performance Summary'!A:A, ROW()), "")
```

### Formulas (Row 2, drag down)

1. **Alert Type (B2):**
   ```
   =IF(A2="","",IF(MAXIFS('Daily Raw Metrics'!B:B, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!C:C, ">"&0)<TEXT(TODAY()-7,"YYYY-MM-DD"), "INACTIVE", IF('Performance Summary'!R2<30, "AT RISK", IF(AND('Performance Summary'!R2<50, COUNTIFS('Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!C:C, ">"&0, 'Daily Raw Metrics'!B:B, ">="&TEXT(TODAY()-7,"YYYY-MM-DD"))<2), "DECLINING", "OK"))))
   ```

2. **Details (C2):**
   ```
   =IF(B2="INACTIVE","No activity in 7+ days",IF(B2="AT RISK","Score below 30",IF(B2="DECLINING","Score <50 and <2 active days this week","")))
   ```

3. **Last Active (D2):**
   ```
   =IF(A2="","",IFERROR(MAXIFS('Daily Raw Metrics'!B:B, 'Daily Raw Metrics'!A:A, A2, 'Daily Raw Metrics'!C:C, ">"&0), "Never"))
   ```

4. **Total Score (E2):**
   ```
   =IF(A2="","",IFERROR('Performance Summary'!R2, 0))
   ```

---

## Tab 5: Config

Set up the following key-value pairs (Column A = Key, Column B = Value):

| Row | Key | Default Value | Description |
|-----|-----|---------------|-------------|
| 1 | base_repos | ed-donner/llm_engineering | Comma-separated list of owner/repo |
| 2 | excluded_users | ed-donner | Comma-separated usernames to exclude |
| 3 | manual_users | | Semi-colon separated: user,fork,base;... |
| 4 | last_poll_timestamp | | Auto-updated by poll.py |
| 5 | bootcamp_start_date | 2026-02-01 | For backfill reference |
| 6 | inactive_threshold_days | 7 | Days without activity = inactive |
| 7 | at_risk_score_threshold | 30 | Score below this = at risk |
| 8 | declining_score_threshold | 50 | Score below this + low recent activity |
| 9 | declining_active_days_min | 2 | Min active days in last week |
| 10 | consistency_max_points | 30 | Max points for consistency |
| 11 | collaboration_max_points | 25 | Max points for collaboration |
| 12 | code_volume_max_points | 25 | Max points for code volume |
| 13 | quality_max_points | 20 | Max points for quality |
| 14 | pr_points_each | 2 | Points per PR opened |
| 15 | review_points_each | 1.5 | Points per review comment |
| 16 | issue_points_each | 1 | Points per issue opened |
| 17 | comment_points_each | 0.5 | Points per comment |
| 18 | lines_added_max_scale | 500 | Lines added for max score |
| 19 | lines_deleted_max_scale | 200 | Lines deleted for max score |
| 20 | merge_rate_max_points | 15 | Max points from merge rate |
| 21 | feedback_max_points | 5 | Max points from feedback |
