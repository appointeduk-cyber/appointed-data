#!/usr/bin/env python3
"""
Appointed public data builder.

Downloads UK corporate insolvency notices from The Gazette (official public
record), assigns each to a UK region using the map point The Gazette attaches
to the notice, and publishes AGGREGATED weekly counts only.

What is published (docs/data/):
  weekly_region.csv   week_start, notice_type, region, count
  weekly_uk.csv       week_start, notice_type, count, located, unlocated
  summary.json        latest complete week vs each region's own 52-week average
  meta.json           when it ran, coverage, definitions, sources

What is NOT published: company names, notice text, addresses or map points.
Map points are only used in memory (and in a private build cache) to find the
region, then thrown away.

Runs on GitHub Actions. Standard library only.
"""
import argparse, csv, datetime as dt, json, os, sys, time, urllib.parse, urllib.request, urllib.error
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data")
CHUNKS = os.path.join(ROOT, "docs", "data", "monthly")      # aggregated monthly chunks (resumable backfill)
CACHE = os.path.join(ROOT, ".cache")                        # private: NOT committed (see .gitignore)
GEO_CACHE = os.path.join(CACHE, "geo.csv")

UA = "AppointedDataBot/1.0 (+https://github.com/appointeduk-cyber/appointed-data; appointeduk@gmail.com)"
GAZETTE = "https://www.thegazette.co.uk/all-notices/notice/data.json"
POSTCODES = "https://api.postcodes.io/postcodes"

# Gazette notice codes counted. Solvent closures (members' voluntary liquidation, code 2432) are excluded.
TYPES = {
    "2410": "Administration",
    "2421": "Administrative receivership",
    "2423": "Receivership",
    "2443": "Creditors' voluntary liquidation",
    "2452": "Winding-up order",
    "2450": "Winding-up petition",
    "2603": "Disclaimer",
}
REGIONS = ["North East", "North West", "Yorkshire and The Humber", "East Midlands", "West Midlands",
           "East of England", "London", "South East", "South West", "Wales", "Scotland", "Northern Ireland"]
UNKNOWN = "Unknown"

GAZ_DELAY = 1.2      # seconds between Gazette requests (be polite)
PC_DELAY = 0.3


def log(*a):
    print(*a, flush=True)


def http(url, data=None, tries=6, delay=GAZ_DELAY):
    body = None
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    wait = 5
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            time.sleep(delay)
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                ra = e.headers.get("Retry-After")
                pause = int(ra) if ra and ra.isdigit() else wait
                log(f"  HTTP {e.code}, waiting {pause}s ({attempt + 1}/{tries})")
                time.sleep(pause); wait = min(wait * 2, 300); continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            log(f"  network/parse error {e!r}, waiting {wait}s ({attempt + 1}/{tries})")
            time.sleep(wait); wait = min(wait * 2, 300)
    raise RuntimeError(f"giving up on {url}")


def find_entries(doc):
    """Return (entries, total) from a Gazette data.json response, tolerant of layout."""
    total = None
    if isinstance(doc, dict):
        for k in ("f:total", "total"):
            if k in doc:
                try: total = int(doc[k])
                except (TypeError, ValueError): pass
        ent = doc.get("entry")
        if ent is None and isinstance(doc.get("feed"), dict):
            return find_entries(doc["feed"])
        if isinstance(ent, dict): ent = [ent]
        return (ent or []), total
    return [], total


def gazette_month(code, start, end):
    """All notices of one code published between start and end (inclusive dates)."""
    out, page, total = [], 1, None
    while True:
        q = {"noticetypes": code, "start-publish-date": start.isoformat(), "end-publish-date": end.isoformat(),
             "results-page-size": "100", "results-page": str(page), "sort-by": "oldest-date"}
        doc = http(GAZETTE + "?" + urllib.parse.urlencode(q))
        ents, t = find_entries(doc)
        if total is None: total = t
        for e in ents:
            if str(e.get("f:notice-code", code)) != code:
                continue
            pub = (e.get("published") or e.get("updated") or "")[:10]
            gp = e.get("geo:Point") or {}
            try:
                lat, lon = float(gp.get("geo:lat")), float(gp.get("geo:long"))
            except (TypeError, ValueError):
                lat = lon = None
            out.append({"id": e.get("id", ""), "date": pub, "lat": lat, "lon": lon})
        if not ents or len(ents) < 100 or (total is not None and page * 100 >= total):
            break
        page += 1
        if page > 200:
            log(f"  WARNING: stopped paging at 200 for {code} {start}"); break
    # de-duplicate by notice id
    seen, uniq = set(), []
    for r in out:
        if r["id"] in seen: continue
        seen.add(r["id"]); uniq.append(r)
    return uniq, total


# ---------- region lookup (postcodes.io reverse geocode, cached privately) ----------
def load_geo():
    m = {}
    if os.path.exists(GEO_CACHE):
        with open(GEO_CACHE, newline="") as f:
            for row in csv.reader(f):
                if len(row) == 2: m[row[0]] = row[1]
    return m


def save_geo(m):
    os.makedirs(CACHE, exist_ok=True)
    with open(GEO_CACHE, "w", newline="") as f:
        w = csv.writer(f)
        for k, v in m.items(): w.writerow([k, v])


def key(lat, lon):
    return f"{lat:.4f},{lon:.4f}"


def region_of(res):
    if not res: return UNKNOWN
    r = res[0]
    country = r.get("country")
    if country == "England":
        reg = r.get("region")
        return reg if reg in REGIONS else UNKNOWN
    if country in ("Scotland", "Wales", "Northern Ireland"):
        return country
    return UNKNOWN


def geocode(points, cache):
    todo = sorted({key(a, b) for a, b in points if a is not None and key(a, b) not in cache})
    for i in range(0, len(todo), 100):
        batch = todo[i:i + 100]
        body = {"geolocations": [{"latitude": float(k.split(",")[0]), "longitude": float(k.split(",")[1]),
                                  "radius": 2000, "limit": 1} for k in batch]}
        doc = http(POSTCODES, data=body, delay=PC_DELAY)
        results = doc.get("result") or []
        for k, item in zip(batch, results):
            cache[k] = region_of((item or {}).get("result"))
    return cache


# ---------- dates ----------
def monday(d):
    return d - dt.timedelta(days=d.weekday())


def months(start, end):
    d = start.replace(day=1)
    while d <= end:
        nxt = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        yield d, min(nxt - dt.timedelta(days=1), end)
        d = nxt


# ---------- build ----------
def build_month(m_start, m_end, cache):
    rows = defaultdict(int)          # (week_start, code, region) -> count
    stats = {}
    for code in TYPES:
        notices, total = gazette_month(code, m_start, m_end)
        cache = geocode([(n["lat"], n["lon"]) for n in notices], cache)
        located = 0
        for n in notices:
            try: d = dt.date.fromisoformat(n["date"])
            except ValueError: continue
            reg = cache.get(key(n["lat"], n["lon"]), UNKNOWN) if n["lat"] is not None else UNKNOWN
            if reg != UNKNOWN: located += 1
            rows[(monday(d).isoformat(), code, reg)] += 1
        stats[code] = {"notices": len(notices), "gazette_total": total, "located": located}
        log(f"  {m_start:%Y-%m} {code} {TYPES[code]}: {len(notices)} notices, {located} located")
    return rows, stats, cache


def write_chunk(month, rows, stats):
    os.makedirs(CHUNKS, exist_ok=True)
    with open(os.path.join(CHUNKS, f"{month}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["week_start", "code", "region", "count"])
        for (wk, code, reg), c in sorted(rows.items()):
            w.writerow([wk, code, reg, c])
    with open(os.path.join(CHUNKS, f"{month}.stats.json"), "w") as f:
        json.dump(stats, f, indent=1)


def assemble(today):
    """Combine monthly chunks into the published files."""
    agg = defaultdict(int)
    stats = {}
    for fn in sorted(os.listdir(CHUNKS)):
        if fn.endswith(".csv"):
            with open(os.path.join(CHUNKS, fn), newline="") as f:
                for r in csv.DictReader(f):
                    agg[(r["week_start"], r["code"], r["region"])] += int(r["count"])
        elif fn.endswith(".stats.json"):
            stats[fn[:7]] = json.load(open(os.path.join(CHUNKS, fn)))

    weeks = sorted({k[0] for k in agg})
    this_monday = monday(today).isoformat()
    complete = [w for w in weeks if w < this_monday]

    with open(os.path.join(OUT, "weekly_region.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["week_start", "notice_type", "region", "count"])
        for wk in weeks:
            for code, name in TYPES.items():
                for reg in REGIONS + [UNKNOWN]:
                    w.writerow([wk, name, reg, agg.get((wk, code, reg), 0)])

    with open(os.path.join(OUT, "weekly_uk.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["week_start", "notice_type", "count", "located", "unlocated"])
        for wk in weeks:
            for code, name in TYPES.items():
                tot = sum(agg.get((wk, code, r), 0) for r in REGIONS + [UNKNOWN])
                unl = agg.get((wk, code, UNKNOWN), 0)
                w.writerow([wk, name, tot, tot - unl, unl])

    # summary: latest complete week vs own trailing 52-week average (the 52 weeks BEFORE it)
    summary = {"latest_week": None, "regions": {}, "uk": {}}
    if len(complete) >= 2:
        lw = complete[-1]; base = complete[-53:-1]
        summary["latest_week"] = lw
        summary["baseline_weeks"] = len(base)
        insolv = [c for c in TYPES if c != "2450" and c != "2603"]   # headline = insolvencies, excl. petitions/disclaimers
        for reg in REGIONS:
            now = sum(agg.get((lw, c, reg), 0) for c in insolv)
            avg = sum(agg.get((b, c, reg), 0) for b in base for c in insolv) / max(len(base), 1)
            summary["regions"][reg] = {"this_week": now, "avg_52w": round(avg, 2),
                                       "vs_usual_pct": round((now / avg - 1) * 100) if avg else None}
        for code, name in TYPES.items():
            now = sum(agg.get((lw, code, r), 0) for r in REGIONS + [UNKNOWN])
            avg = sum(agg.get((b, code, r), 0) for b in base for r in REGIONS + [UNKNOWN]) / max(len(base), 1)
            summary["uk"][name] = {"this_week": now, "avg_52w": round(avg, 2),
                                   "vs_usual_pct": round((now / avg - 1) * 100) if avg else None}
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)

    tot = sum(s["notices"] for m in stats.values() for s in m.values())
    loc = sum(s["located"] for m in stats.values() for s in m.values())
    meta = {
        "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "first_week": weeks[0] if weeks else None,
        "last_week": weeks[-1] if weeks else None,
        "last_complete_week": complete[-1] if complete else None,
        "current_week_is_partial": bool(weeks and weeks[-1] >= this_monday),
        "notices_counted": tot,
        "share_with_region": round(loc / tot, 4) if tot else None,
        "notice_types": TYPES,
        "regions": REGIONS + [UNKNOWN],
        "definitions": {
            "week_start": "Monday of the week the notice was published in The Gazette (not the date of the insolvency itself).",
            "region": "From the map point The Gazette attaches to each notice, matched to the nearest postcode (postcodes.io, ONS data). 'Unknown' where the notice has no map point or none within 2km.",
            "headline_insolvencies": "Administration + receiverships + creditors' voluntary liquidation + winding-up orders. Petitions and disclaimers are reported separately; members' voluntary liquidations (solvent) are excluded.",
            "covid_restrictions": "Winding-up petitions were restricted by law from 27 April 2020 to 31 March 2022 (Corporate Insolvency and Governance Act 2020 and follow-on regulations). Petition and winding-up order numbers in that period are artificially low.",
        },
        "covid_restriction_period": {"start": "2020-04-27", "end": "2022-03-31"},
        "sources": ["The Gazette (thegazette.co.uk), Open Government Licence; notice counts only, no personal data reused",
                    "postcodes.io (ONS Postcode Directory), Open Government Licence"],
        "monthly_stats": stats,
    }
    with open(os.path.join(OUT, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    log(f"assembled {len(weeks)} weeks, {tot} notices, {loc} located")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default=None, help="default: today")
    ap.add_argument("--max-minutes", type=float, default=300)
    ap.add_argument("--refresh-days", type=int, default=45, help="re-fetch months ending within this many days")
    a = ap.parse_args()
    today = dt.date.today()
    start = dt.date.fromisoformat(a.start)
    end = dt.date.fromisoformat(a.end) if a.end else today
    os.makedirs(OUT, exist_ok=True); os.makedirs(CHUNKS, exist_ok=True)
    t0 = time.time()
    cache = load_geo()
    done_all = True
    for m_start, m_end in months(start, end):
        tag = f"{m_start:%Y-%m}"
        exists = os.path.exists(os.path.join(CHUNKS, f"{tag}.csv"))
        fresh = (today - m_end).days <= a.refresh_days
        if exists and not fresh:
            continue
        if (time.time() - t0) / 60 > a.max_minutes:
            log(f"time budget reached before {tag}; will continue next run"); done_all = False; break
        log(f"month {tag} ({m_start} to {m_end})")
        rows, stats, cache = build_month(m_start, m_end, cache)
        write_chunk(tag, rows, stats)
        save_geo(cache)
    assemble(today)
    with open(os.path.join(OUT, "backfill_status.json"), "w") as f:
        json.dump({"complete": done_all, "checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}, f)
    log("backfill complete" if done_all else "backfill partial")


if __name__ == "__main__":
    main()
