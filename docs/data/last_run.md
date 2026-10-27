# Last run

- UTC: 2026-10-27T03:12:17Z
- Trigger: schedule

```
month 2026-09
  2026-09 2410: 124 notices
  2026-09 2421: 0 notices
  2026-09 2423: 0 notices
  2026-09 2441: 1495 notices
  2026-09 2443: 1503 notices
  2026-09 2450: 534 notices
  2026-09 2451: 1 notices
  2026-09 2452: 332 notices
  2026-09 2603: 99 notices
month 2026-10
  2026-10 2410: 125 notices
  2026-10 2421: 0 notices
  2026-10 2423: 0 notices
  network/parse error JSONDecodeError('Expecting value: line 1 column 1 (char 0)'), waiting 10s (1/6)
  network/parse error JSONDecodeError('Expecting value: line 1 column 1 (char 0)'), waiting 20s (2/6)
  network/parse error JSONDecodeError('Expecting value: line 1 column 1 (char 0)'), waiting 40s (3/6)
  network/parse error JSONDecodeError('Expecting value: line 1 column 1 (char 0)'), waiting 80s (4/6)
  network/parse error JSONDecodeError('Expecting value: line 1 column 1 (char 0)'), waiting 160s (5/6)
  network/parse error JSONDecodeError('Expecting value: line 1 column 1 (char 0)'), waiting 300s (6/6)
Traceback (most recent call last):
  File "/home/runner/work/appointed-data/appointed-data/pipeline/build.py", line 635, in <module>
    main()
  File "/home/runner/work/appointed-data/appointed-data/pipeline/build.py", line 607, in main
    rows, totals, geo = fetch_month(ms, me, geo)
                        ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/runner/work/appointed-data/appointed-data/pipeline/build.py", line 216, in fetch_month
    ents, t = entries_of(http(GAZETTE + "?" + urllib.parse.urlencode(q)))
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/runner/work/appointed-data/appointed-data/pipeline/build.py", line 103, in http
    raise RuntimeError(f"giving up on {url}")
RuntimeError: giving up on https://www.thegazette.co.uk/all-notices/notice/data.json?noticetypes=2441&edition=London&start-publish-date=2026-10-01&end-publish-date=2026-10-27&results-page-size=100&results-page=5&sort-by=oldest-date
official: company-insolvencies-september-2026, 81 months; reconciled 243 component-months
  ADM: {'months_compared_since_apr_2022': 54, 'ratio_mean': 1.02, 'ratio_sd': 0.161, 'ratio_min': 0.665, 'ratio_max': 1.495, 'share_of_months_within_10pct_of_mean': 0.5, 'corr_monthly_changes': 0.642, 'corr_3month_changes': 0.786, 'latest_month': '2026-09', 'latest_ratio': 1.14}
  CVL: {'months_compared_since_apr_2022': 54, 'ratio_mean': 1.02, 'ratio_sd': 0.107, 'ratio_min': 0.756, 'ratio_max': 1.281, 'share_of_months_within_10pct_of_mean': 0.704, 'corr_monthly_changes': 0.479, 'corr_3month_changes': 0.554, 'latest_month': '2026-09', 'latest_ratio': 1.03}
  WUO: {'months_compared_since_apr_2022': 54, 'ratio_mean': 1.009, 'ratio_sd': 0.23, 'ratio_min': 0.203, 'ratio_max': 1.447, 'share_of_months_within_10pct_of_mean': 0.37, 'corr_monthly_changes': 0.168, 'corr_3month_changes': 0.247, 'latest_month': '2026-09', 'latest_ratio': 0.91}
charts: regional map for week starting 2026-10-19
```
