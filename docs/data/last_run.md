# Last run

- UTC: 2026-10-20T05:11:13Z
- Trigger: schedule

```
  2022-04 2603: 101 notices
month 2022-05
  2022-05 2410: 79 notices
  2022-05 2421: 0 notices
  2022-05 2423: 0 notices
  2022-05 2441: 1690 notices
  2022-05 2443: 1712 notices
  2022-05 2450: 246 notices
  2022-05 2451: 1 notices
  2022-05 2452: 165 notices
  2022-05 2603: 105 notices
month 2022-06
  2022-06 2410: 104 notices
  2022-06 2421: 1 notices
  2022-06 2423: 0 notices
  2022-06 2441: 1536 notices
  2022-06 2443: 1562 notices
  2022-06 2450: 214 notices
  2022-06 2451: 0 notices
  2022-06 2452: 151 notices
  2022-06 2603: 69 notices
month 2022-07
  2022-07 2410: 94 notices
  2022-07 2421: 0 notices
  2022-07 2423: 0 notices
  2022-07 2441: 1718 notices
  2022-07 2443: 1766 notices
  2022-07 2450: 257 notices
  2022-07 2451: 1 notices
  2022-07 2452: 169 notices
  2022-07 2603: 80 notices
month 2022-08
  2022-08 2410: 120 notices
  2022-08 2421: 0 notices
  2022-08 2423: 0 notices
  2022-08 2441: 1683 notices
  2022-08 2443: 1715 notices
  2022-08 2450: 323 notices
  2022-08 2451: 3 notices
  2022-08 2452: 183 notices
  2022-08 2603: 80 notices
month 2022-09
  2022-09 2410: 113 notices
  2022-09 2421: 0 notices
  2022-09 2423: 0 notices
  2022-09 2441: 1585 notices
  2022-09 2443: 1629 notices
  2022-09 2450: 398 notices
  2022-09 2451: 0 notices
  2022-09 2452: 215 notices
  2022-09 2603: 74 notices
month 2022-10
  2022-10 2410: 108 notices
  2022-10 2421: 0 notices
  2022-10 2423: 0 notices
  2022-10 2441: 1651 notices
  2022-10 2443: 1682 notices
  2022-10 2450: 405 notices
  2022-10 2451: 1 notices
  2022-10 2452: 181 notices
  2022-10 2603: 55 notices
month 2022-11
  2022-11 2410: 160 notices
  2022-11 2421: 0 notices
  2022-11 2423: 0 notices
  2022-11 2441: 1789 notices
  2022-11 2443: 1814 notices
  2022-11 2450: 474 notices
  2022-11 2451: 1 notices
  2022-11 2452: 307 notices
  2022-11 2603: 100 notices
month 2022-12
  2022-12 2410: 124 notices
  2022-12 2421: 0 notices
  2022-12 2423: 0 notices
  2022-12 2441: 1882 notices
  2022-12 2443: 1915 notices
  2022-12 2450: 346 notices
  2022-12 2451: 0 notices
  2022-12 2452: 241 notices
  2022-12 2603: 82 notices
month 2023-01
  2023-01 2410: 76 notices
  2023-01 2421: 0 notices
  2023-01 2423: 0 notices
  2023-01 2441: 1150 notices
  2023-01 2443: 1190 notices
  2023-01 2450: 334 notices
  2023-01 2451: 0 notices
  2023-01 2452: 151 notices
  2023-01 2603: 65 notices
month 2023-02
  2023-02 2410: 118 notices
  2023-02 2421: 0 notices
  2023-02 2423: 0 notices
  2023-02 2441: 1733 notices
  2023-02 2443: 1762 notices
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
RuntimeError: giving up on https://www.thegazette.co.uk/all-notices/notice/data.json?noticetypes=2450&edition=London&start-publish-date=2023-02-01&end-publish-date=2023-02-28&results-page-size=100&results-page=2&sort-by=oldest-date
official: company-insolvencies-august-2026, 80 months; reconciled 240 component-months
  ADM: {'months_compared_since_apr_2022': 53, 'ratio_mean': 1.018, 'ratio_sd': 0.162, 'ratio_min': 0.665, 'ratio_max': 1.495, 'share_of_months_within_10pct_of_mean': 0.491, 'corr_monthly_changes': 0.646, 'corr_3month_changes': 0.763, 'latest_month': '2026-08', 'latest_ratio': 0.794}
  CVL: {'months_compared_since_apr_2022': 53, 'ratio_mean': 1.02, 'ratio_sd': 0.108, 'ratio_min': 0.756, 'ratio_max': 1.281, 'share_of_months_within_10pct_of_mean': 0.698, 'corr_monthly_changes': 0.48, 'corr_3month_changes': 0.554, 'latest_month': '2026-08', 'latest_ratio': 0.956}
  WUO: {'months_compared_since_apr_2022': 53, 'ratio_mean': 1.011, 'ratio_sd': 0.232, 'ratio_min': 0.203, 'ratio_max': 1.447, 'share_of_months_within_10pct_of_mean': 0.358, 'corr_monthly_changes': 0.173, 'corr_3month_changes': 0.247, 'latest_month': '2026-08', 'latest_ratio': 1.151}
charts: regional map for week starting 2026-10-12
```
