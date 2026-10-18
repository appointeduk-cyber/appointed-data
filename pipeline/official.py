#!/usr/bin/env python3
"""
Fetch the Insolvency Service's official monthly company insolvency figures
(long-run CSV, England and Wales, not seasonally adjusted) and reconcile them
against Appointed's Gazette-based monthly counts.

Writes:
  docs/data/official_england_wales.csv   month, administrations, cvl, compulsory_liquidations, admin_to_cvl, total
  docs/data/reconciliation.csv           month, component, appointed, official, ratio
  docs/data/reconciliation_summary.json  per-component ratio statistics, correlation of monthly changes

Important difference: the official series counts by Companies House registration
month (compulsory liquidations by order date); Appointed counts by Gazette
publication week. A stable ratio, not an exact match, is the test.
"""
import csv, datetime as dt, io, json, math, os, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data")
UA = "AppointedDataBot/2.0 (+https://github.com/appointeduk-cyber/appointed-data; appointeduk@gmail.com)"
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
START = "2020-01"
MAP = {"ADM": "admin_ew_nsa", "CVL": "cvl_ew_nsa", "WUO": "compliq_ew_nsa"}


def get(url, as_json=False):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            return json.loads(raw) if as_json else raw
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    return None


def latest_release():
    """Walk back month by month to the newest 'company-insolvencies-<month>-<year>' release."""
    t = dt.date.today()
    y, m = t.year, t.month
    for _ in range(6):
        slug = f"company-insolvencies-{MONTHS[m - 1]}-{y}"
        doc = get(f"https://www.gov.uk/api/content/government/statistics/{slug}", as_json=True)
        if doc:
            for a in (doc.get("details", {}).get("attachments") or []):
                title = (a.get("title") or "").lower()
                if title.startswith("long-run series in csv") and a.get("url"):
                    return slug, a["url"], doc.get("first_published_at")
        m -= 1
        if m == 0: y, m = y - 1, 12
    return None, None, None


def num(x):
    try: return int(float(x))
    except (TypeError, ValueError): return None


def main():
    slug, url, published = latest_release()
    if not url:
        print("official: no release found; leaving files unchanged"); return
    raw = get(url)
    if not raw:
        print("official: download failed; leaving files unchanged"); return
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    off = {}
    for r in rows:
        p = r.get("period", "")
        if p >= START:
            off[p] = {k: num(r.get(c)) for k, c in MAP.items()}
            off[p]["ADM_TO_CVL"] = num(r.get("adcvl_ew_nsa"))
            off[p]["TOTAL"] = num(r.get("total_ew_nsa"))
    with open(os.path.join(OUT, "official_england_wales.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "administrations", "cvl", "compulsory_liquidations", "admin_to_cvl", "total"])
        for p in sorted(off):
            o = off[p]; w.writerow([p, o["ADM"], o["CVL"], o["WUO"], o["ADM_TO_CVL"], o["TOTAL"]])

    ours = {}
    mp = os.path.join(OUT, "monthly_england_wales.csv")
    if os.path.exists(mp):
        for r in csv.DictReader(open(mp)):
            ours[(r["month"], r["component"])] = int(r["count"])
    this_month = dt.date.today().strftime("%Y-%m")
    recon, summ = [], {}
    for comp in MAP:
        pairs = []
        for p in sorted(off):
            if p >= this_month: continue
            a, o = ours.get((p, comp)), off[p][comp]
            if a is None or not o: continue
            ratio = a / o
            recon.append([p, comp, a, o, round(ratio, 3)])
            pairs.append((p, a, o, ratio))
        if len(pairs) < 6: continue
        post = [x for x in pairs if x[0] >= "2022-04"]          # after Covid restrictions
        ratios = [x[3] for x in post]
        mean = sum(ratios) / len(ratios)
        sd = math.sqrt(sum((x - mean) ** 2 for x in ratios) / (len(ratios) - 1)) if len(ratios) > 1 else None
        # correlation of month-on-month changes (levels correlate trivially)
        da = [post[i][1] - post[i - 1][1] for i in range(1, len(post))]
        do = [post[i][2] - post[i - 1][2] for i in range(1, len(post))]
        def corr(x, y):
            if len(x) < 3: return None
            mx, my = sum(x) / len(x), sum(y) / len(y)
            sx = math.sqrt(sum((v - mx) ** 2 for v in x)); sy = math.sqrt(sum((v - my) ** 2 for v in y))
            return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy) if sx and sy else None
        # same on 3-month sums, which damps the registration/publication timing difference
        def roll3(v): return [sum(v[i - 2:i + 1]) for i in range(2, len(v))]
        a3, o3 = roll3([x[1] for x in post]), roll3([x[2] for x in post])
        c3 = corr([a3[i] - a3[i - 1] for i in range(1, len(a3))], [o3[i] - o3[i - 1] for i in range(1, len(o3))])
        summ[comp] = {
            "months_compared_since_apr_2022": len(post),
            "ratio_mean": round(mean, 3), "ratio_sd": round(sd, 3) if sd is not None else None,
            "ratio_min": round(min(ratios), 3), "ratio_max": round(max(ratios), 3),
            "share_of_months_within_10pct_of_mean": round(sum(abs(r - mean) <= 0.1 * mean for r in ratios) / len(ratios), 3),
            "corr_monthly_changes": round(corr(da, do), 3) if corr(da, do) is not None else None,
            "corr_3month_changes": round(c3, 3) if c3 is not None else None,
            "latest_month": post[-1][0], "latest_ratio": round(post[-1][3], 3),
        }
    with open(os.path.join(OUT, "reconciliation.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["month", "component", "appointed", "official", "ratio"]); w.writerows(recon)
    with open(os.path.join(OUT, "reconciliation_summary.json"), "w") as f:
        json.dump({"official_release": slug, "official_published": published, "official_csv": url,
                   "basis_note": "Official: Companies House registration month (compulsory liquidations by order date), England and Wales, not seasonally adjusted. Appointed: London Gazette edition, events dated by publication week, assigned to the calendar month of their first notice.",
                   "components": summ}, f, indent=1)
    print(f"official: {slug}, {len(off)} months; reconciled {len(recon)} component-months")
    for k, v in summ.items(): print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
