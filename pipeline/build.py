#!/usr/bin/env python3
"""
Appointed public data builder, version 2.

Reads UK corporate insolvency notices from The Gazette (London, Edinburgh and
Belfast editions), turns NOTICES into EVENTS (one per company per procedure),
and publishes aggregated weekly counts plus the Appointed distress index.

Stages
  1. fetch     notice-level rows for each month, kept in a PRIVATE build cache
               (.cache/notices/, never committed): notice id, code, edition,
               publication date, company key, region, HMRC-petitioner flag.
  2. events    notices -> events (de-duplicated by company number).
  3. publish   aggregated weekly counts, quality measures, index (docs/data/).

What is published: counts only. No company names, numbers, notice text,
addresses or map points.

Date basis: the free feed does not expose the appointment/order date, so events
are dated by the week the FIRST notice for that event was published.

Standard library only. Runs on GitHub Actions.
"""
import argparse, csv, datetime as dt, json, math, os, re, sys, time, urllib.parse, urllib.request, urllib.error
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data")
CACHE = os.path.join(ROOT, ".cache")
NOTICE_CACHE = os.path.join(CACHE, "notices")
GEO_CACHE = os.path.join(CACHE, "geo.csv")
PRIVATE = os.path.join(CACHE, "private")   # members-only outputs: never under docs/, never committed
METHOD_VERSION = "2.2"

UA = "AppointedDataBot/2.0 (+https://github.com/appointeduk-cyber/appointed-data; appointeduk@gmail.com)"
GAZETTE = "https://www.thegazette.co.uk/all-notices/notice/data.json"
POSTCODES = "https://api.postcodes.io/postcodes"
GAZ_DELAY = 2.0      # Gazette fair-use policy: max 5 requests per 10 seconds
PC_DELAY = 0.3

EDITIONS = {"London": "England and Wales", "Edinburgh": "Scotland", "Belfast": "Northern Ireland"}
CODES = {
    "2410": "Appointment of administrators",
    "2421": "Appointment of administrative receivers",
    "2423": "Appointment of receivers",
    "2441": "CVL resolution for winding up",
    "2443": "CVL appointment of liquidators",
    "2450": "Petition to wind up (company)",
    "2451": "Petition to wind up (partnership)",
    "2452": "Winding-up order (company)",
    "2603": "Notice of disclaimer",
}
REGIONS = ["North East", "North West", "Yorkshire and The Humber", "East Midlands", "West Midlands",
           "East of England", "London", "South East", "South West", "Wales", "Scotland", "Northern Ireland"]
UNKNOWN = "Unknown"

# components: headline (ADM, CVL, WUO); separate indicator (PET); memo items
COMPONENTS = {
    "ADM": "Administrations",
    "CVL": "Creditors' voluntary liquidations",
    "WUO": "Winding-up orders",
    "PET": "Winding-up petitions",
    "PET_HMRC": "Winding-up petitions brought by HMRC",
    "ADM_TO_CVL": "Administrations moving to CVL (excluded from CVL)",
    "MEMO_AR": "Administrative receiverships (memo)",
    "MEMO_REC": "Receiver appointments (memo, not legally required to be gazetted)",
    "MEMO_DIS": "Disclaimers (memo, not legally required to be gazetted)",
}
HEADLINE = ["ADM", "CVL", "WUO"]
BASELINE = ("2024-01-01", "2025-12-31")      # "recent normal" = 100
PET_START = "2022-04-04"                     # first Monday after petition restrictions ended (31 Mar 2022)
COVID_RESTRICTED = ("2020-03-01", "2022-03-31")
MIN_CELL = 20


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- HTTP
def http(url, data=None, tries=6, delay=GAZ_DELAY):
    body = None
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if data is not None:
        body = json.dumps(data).encode(); headers["Content-Type"] = "application/json"
    wait = 10
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=60) as r:
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


def entries_of(doc):
    total = None
    if isinstance(doc, dict):
        try: total = int(doc.get("f:total"))
        except (TypeError, ValueError): pass
        ent = doc.get("entry")
        if ent is None and isinstance(doc.get("feed"), dict):
            return entries_of(doc["feed"])
        if isinstance(ent, dict): ent = [ent]
        return ent or [], total
    return [], total


# ---------------------------------------------------------------- parsing
TAG = re.compile(r"<[^>]+>")
NUM = re.compile(r"(?:company|registered|registration)\s*(?:number|no\.?)\s*[:\-]?\s*"
                 r"((?:SC|NI|OC|SO|NC|SL|FC|SE|R0|GE|LP|IP|SP|RS|AC|CE|CS|NF|NL|SF|SA|SR|SZ|ZC)?\s?\d{5,8})", re.I)
HMRC = re.compile(r"revenue\s*(?:and|&)\s*customs|\bHMRC\b|H\s?M\s?R\s?C", re.I)
PETITIONER = re.compile(r"petition(?:er)?\b", re.I)
SUFFIX = re.compile(r"\b(LIMITED|LTD|PLC|LLP|L\.L\.P\.|CIC|COMPANY|CO)\b\.?", re.I)


def text_of(e):
    c = e.get("content")
    if isinstance(c, dict): c = c.get("#text") or c.get("$") or json.dumps(c)
    return TAG.sub(" ", str(c or ""))


def company_key(e, txt):
    m = NUM.search(txt)
    if m:
        n = re.sub(r"\s", "", m.group(1)).upper()
        if n.isdigit(): n = n.zfill(8)
        return "C:" + n, True
    title = str(e.get("title") or "").upper()
    title = SUFFIX.sub("", re.sub(r"[^A-Z0-9 &]", " ", title))
    return "N:" + re.sub(r"\s+", " ", title).strip(), False


def hmrc_flag(code, txt):
    if code not in ("2450", "2451"): return ""
    if HMRC.search(txt): return "1"
    return "0" if PETITIONER.search(txt) else "?"   # "?" = petitioner not visible in the truncated text


# ---------------------------------------------------------------- geo
def load_geo():
    """Map point -> "region|constituency". Older cache rows hold the region only;
    those points are looked up again so the constituency can be added."""
    m = {}
    if os.path.exists(GEO_CACHE):
        with open(GEO_CACHE, newline="") as f:
            for row in csv.reader(f):
                if len(row) == 2 and "|" in row[1]: m[row[0]] = row[1]
    return m


def geo_split(v):
    reg, _, con = (v or "").partition("|")
    return (reg or UNKNOWN), (con or UNKNOWN)


def save_geo(m):
    os.makedirs(CACHE, exist_ok=True)
    with open(GEO_CACHE, "w", newline="") as f:
        csv.writer(f).writerows(m.items())


def gkey(lat, lon): return f"{lat:.4f},{lon:.4f}"


def region_of(res):
    if not res: return UNKNOWN
    r = res[0]; c = r.get("country")
    if c == "England":
        return r.get("region") if r.get("region") in REGIONS else UNKNOWN
    return c if c in ("Scotland", "Wales", "Northern Ireland") else UNKNOWN


def geocode(points, cache):
    todo = sorted({gkey(a, b) for a, b in points if a is not None and gkey(a, b) not in cache})
    for i in range(0, len(todo), 100):
        batch = todo[i:i + 100]
        body = {"geolocations": [{"latitude": float(k.split(",")[0]), "longitude": float(k.split(",")[1]),
                                  "radius": 2000, "limit": 1} for k in batch]}
        doc = http(POSTCODES, data=body, delay=PC_DELAY)
        for k, item in zip(batch, doc.get("result") or []):
            res = (item or {}).get("result")
            con = UNKNOWN
            if res:
                con = res[0].get("parliamentary_constituency_2024") or res[0].get("parliamentary_constituency") or UNKNOWN
            cache[k] = f"{region_of(res)}|{con.replace('|', ' ')}"
    return cache


# ---------------------------------------------------------------- stage 1: fetch
FIELDS = ["id", "code", "edition", "date", "key", "has_number", "region", "located", "hmrc", "constituency", "pt"]
OFFICE_MIN = 20   # a map point shared by this many different companies is an office address, not where they traded
CONST_START = "2024-07"   # Westminster boundaries in force from the July 2024 general election


def fetch_month(m_start, m_end, geo):
    rows, seen, totals = [], set(), {}
    for code in CODES:
        for ed in EDITIONS:
            page, got, total = 1, 0, None
            while True:
                q = {"noticetypes": code, "edition": ed, "start-publish-date": m_start.isoformat(),
                     "end-publish-date": m_end.isoformat(), "results-page-size": "100",
                     "results-page": str(page), "sort-by": "oldest-date"}
                ents, t = entries_of(http(GAZETTE + "?" + urllib.parse.urlencode(q)))
                if total is None: total = t
                batch = []
                for e in ents:
                    if str(e.get("f:notice-code", code)) != code: continue
                    nid = str(e.get("id", ""))
                    if not nid or nid in seen: continue
                    seen.add(nid)
                    gp = e.get("geo:Point") or {}
                    try: lat, lon = float(gp.get("geo:lat")), float(gp.get("geo:long"))
                    except (TypeError, ValueError): lat = lon = None
                    txt = text_of(e)
                    key, has_num = company_key(e, txt)
                    batch.append({"id": nid.rsplit("/", 1)[-1], "code": code, "edition": ed,
                                  "date": (e.get("published") or e.get("updated") or "")[:10],
                                  "key": key, "has_number": "1" if has_num else "0",
                                  "_lat": lat, "_lon": lon, "hmrc": hmrc_flag(code, txt)})
                geo = geocode([(b["_lat"], b["_lon"]) for b in batch], geo)
                for b in batch:
                    reg, con = geo_split(geo.get(gkey(b["_lat"], b["_lon"]))) if b["_lat"] is not None else (UNKNOWN, UNKNOWN)
                    b["constituency"] = con
                    b["pt"] = gkey(b["_lat"], b["_lon"]) if b["_lat"] is not None else ""
                    b["located"] = "1" if reg != UNKNOWN else "0"
                    if reg == UNKNOWN and ed in ("Edinburgh", "Belfast"):
                        reg = EDITIONS[ed]          # nation is certain from the edition even without a map point
                    b["region"] = reg
                    del b["_lat"], b["_lon"]
                rows += batch; got += len(ents)
                if not ents or len(ents) < 100 or (total is not None and page * 100 >= total): break
                page += 1
                if page > 300: log(f"  WARNING paging cap {code} {ed} {m_start}"); break
            totals[f"{code}/{ed}"] = {"gazette_total": total, "rows": got}
        log(f"  {m_start:%Y-%m} {code}: {sum(1 for r in rows if r['code'] == code)} notices")
    return rows, totals, geo


def write_notice_cache(tag, rows, totals):
    os.makedirs(NOTICE_CACHE, exist_ok=True)
    with open(os.path.join(NOTICE_CACHE, f"{tag}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    with open(os.path.join(NOTICE_CACHE, f"{tag}.totals.json"), "w") as f:
        json.dump(totals, f)


def load_notices():
    rows = []
    for fn in sorted(os.listdir(NOTICE_CACHE)):
        if fn.endswith(".csv"):
            with open(os.path.join(NOTICE_CACHE, fn), newline="") as f:
                rows += list(csv.DictReader(f))
    return rows


# ---------------------------------------------------------------- stage 2: events
def d(s): return dt.date.fromisoformat(s)
def monday(x): return x - dt.timedelta(days=x.weekday())


def easter(y):
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31; da = (h + l - 7 * m + 114) % 31 + 1
    return dt.date(y, mo, da)


def holiday_week(wk):
    """True if the Monday-start week includes Christmas/New Year (24 Dec - 14 Jan, allowing for the
    slow restart after New Year) or the Easter bank holidays, when courts and insolvency firms largely
    stop and far fewer notices appear."""
    days = [wk + dt.timedelta(days=j) for j in range(7)]
    for x in days:
        if (x.month == 12 and x.day >= 24) or (x.month == 1 and x.day <= 14): return True
        e = easter(x.year)
        if x in (e - dt.timedelta(days=2), e + dt.timedelta(days=1)): return True
    return False


def build_events(notices):
    """Collapse notices into events. Returns list of (component, date, edition, region, extra)."""
    by_code = defaultdict(list)
    for n in notices:
        if n["date"]: by_code[n["code"]].append(n)
    for v in by_code.values(): v.sort(key=lambda r: r["date"])
    events, q = [], Counter()

    def collapse(rows, window_days, comp):
        last = {}
        out = []
        for r in rows:
            k, t = r["key"], d(r["date"])
            if k in last and (t - last[k]).days <= window_days:
                q[f"{comp}_duplicates"] += 1
                continue
            last[k] = t
            out.append(r)
        q[f"{comp}_notices"] += len(rows); q[f"{comp}_events"] += len(out)
        return out

    def ev(comp, r, extra=""):
        events.append((comp, r["date"], r["edition"], r["region"], extra, r.get("constituency") or ""))

    adm = collapse(by_code["2410"], 365, "ADM")
    adm_dates = defaultdict(list)
    for r in adm:
        ev("ADM", r)
        adm_dates[r["key"]].append(d(r["date"]))

    # CVLs: the liquidator appointment notice (2443) carries a company number in >99% of cases.
    # Resolution notices (2441) are used only when they carry a number too; most do not, and a
    # name-keyed resolution can't be matched to its numbered appointment notice, so including it
    # double-counted about three in four CVLs (v2.0 counted ~1.76x the official figure).
    cvl_rows = sorted(by_code["2443"] + [r for r in by_code["2441"] if r["has_number"] == "1"],
                      key=lambda r: r["date"])
    for r in collapse(cvl_rows, 120, "CVL"):
        t = d(r["date"])
        if any(0 <= (t - a).days <= 548 for a in adm_dates.get(r["key"], [])):
            ev("ADM_TO_CVL", r); continue
        ev("CVL", r)

    for r in collapse(by_code["2452"], 365, "WUO"):
        ev("WUO", r)

    pet_rows = sorted(by_code["2450"] + by_code["2451"], key=lambda r: r["date"])
    for r in collapse(pet_rows, 180, "PET"):
        ev("PET", r, r["hmrc"])
        if r["hmrc"] == "1":
            ev("PET_HMRC", r)
        q[f"PET_hmrc_{ {'1': 'yes', '0': 'no', '?': 'unknown'}.get(r['hmrc'], 'unknown') }"] += 1

    for code, comp in (("2421", "MEMO_AR"), ("2423", "MEMO_REC"), ("2603", "MEMO_DIS")):
        for r in collapse(by_code[code], 365, comp):
            ev(comp, r)
    return events, q


# ---------------------------------------------------------------- stage 3: publish
def wsum(series, weeks, i, n):
    return sum(series.get(weeks[j], 0) for j in range(max(0, i - n + 1), i + 1))


def publish(notices, events, q, today, fetch_totals):
    os.makedirs(OUT, exist_ok=True)
    this_monday = monday(today)
    first = monday(d(min(n["date"] for n in notices if n["date"])))
    weeks, w = [], first
    while w < this_monday:            # complete weeks only
        weeks.append(w.isoformat()); w += dt.timedelta(days=7)
    wset = set(weeks)

    # weekly counts: component x nation x region
    cnt = Counter()
    for comp, date, ed, reg, *_ in events:
        wk = monday(d(date)).isoformat()
        if wk in wset: cnt[(wk, comp, EDITIONS[ed], reg)] += 1
    nations = list(EDITIONS.values())
    with open(os.path.join(OUT, "weekly_components.csv"), "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["week_start", "component", "nation", "region", "count"])
        for (wk, comp, nat, reg), c in sorted(cnt.items()):
            wr.writerow([wk, comp, nat, reg, c])

    # monthly England & Wales (London edition) for reconciliation with Insolvency Service
    mon = Counter()
    for comp, date, ed, reg, *_ in events:
        if ed == "London": mon[(date[:7], comp)] += 1
    with open(os.path.join(OUT, "monthly_england_wales.csv"), "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["month", "component", "count"])
        for (m, comp), c in sorted(mon.items()): wr.writerow([m, comp, c])

    # national (UK) weekly series per component
    uk = {c: Counter() for c in COMPONENTS}
    reg_hl = {r: Counter() for r in REGIONS + [UNKNOWN]}
    for (wk, comp, nat, reg), c in cnt.items():
        uk[comp][wk] += c
        if comp in HEADLINE: reg_hl[reg][wk] += c

    base_idx = [i for i, wk in enumerate(weeks) if BASELINE[0] <= wk <= BASELINE[1]]
    have_base = len(base_idx) >= 52
    idx_rows, meta_idx = [], {}
    if have_base:
        S4 = {k: [wsum(uk[k], weeks, i, 4) for i in range(len(weeks))] for k in COMPONENTS}
        S13 = {k: [wsum(uk[k], weeks, i, 13) for i in range(len(weeks))] for k in COMPONENTS}
        B4 = {k: sum(S4[k][i] for i in base_idx) / len(base_idx) for k in COMPONENTS}
        # volatility-equalised weights: 1 / sd of 13-week log changes during the baseline
        sds = {}
        for k in HEADLINE:
            ch = [math.log(S13[k][i] / S13[k][i - 13]) for i in base_idx if i >= 13 and S13[k][i] > 0 and S13[k][i - 13] > 0]
            m = sum(ch) / len(ch)
            sds[k] = math.sqrt(sum((x - m) ** 2 for x in ch) / (len(ch) - 1))
        inv = {k: 1 / sds[k] for k in HEADLINE}
        wts = {k: inv[k] / sum(inv.values()) for k in HEADLINE}
        Bpet_idx = [i for i in base_idx if weeks[i] >= PET_START]
        Bpet = sum(S4["PET"][i] for i in Bpet_idx) / len(Bpet_idx)
        # The free feed's notice summary is truncated before the petitioner's name in most notices,
        # so HMRC can't be detected reliably. Publish the share only if detection actually works.
        hmrc_ok = sum(uk["PET_HMRC"].values()) >= 0.05 * max(1, sum(uk["PET"].values()))
        for i, wk in enumerate(weeks):
            if i < 3: continue
            ci = {k: 100 * S4[k][i] / B4[k] if B4[k] else None for k in HEADLINE}
            head = sum(wts[k] * ci[k] for k in HEADLINE)
            eq = sum(ci.values()) / 3
            plain = 100 * sum(S4[k][i] for k in HEADLINE) / sum(B4[k] for k in HEADLINE)
            pet = 100 * S4["PET"][i] / Bpet if wk >= PET_START else None
            hm = S4["PET_HMRC"][i] / S4["PET"][i] if hmrc_ok and wk >= PET_START and S4["PET"][i] else None
            idx_rows.append({
                "week_start": wk, "index": round(head, 1), "equal_weight": round(eq, 1), "plain_count": round(plain, 1),
                "administrations": round(ci["ADM"], 1), "cvl": round(ci["CVL"], 1), "winding_up_orders": round(ci["WUO"], 1),
                "events_4wk": sum(S4[k][i] for k in HEADLINE),
                "petitions_index": round(pet, 1) if pet is not None else "",
                "petitions_hmrc_share_detected": round(hm, 3) if hm is not None else "",
                "provisional": "1" if i >= len(weeks) - 4 else "0",
                "restricted_period": "1" if COVID_RESTRICTED[0] <= wk <= COVID_RESTRICTED[1] else "0",
                "holiday_affected": "1" if any(holiday_week(d(weeks[j])) for j in range(max(0, i - 3), i + 1)) else "0",
            })
        with open(os.path.join(OUT, "index_weekly.csv"), "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(idx_rows[0].keys())); wr.writeheader(); wr.writerows(idx_rows)

        # regional index on 13-week sums, suppressed under MIN_CELL; plus diffusion
        R13 = {r: [wsum(reg_hl[r], weeks, i, 13) for i in range(len(weeks))] for r in reg_hl}
        RB = {r: sum(R13[r][i] for i in base_idx) / len(base_idx) for r in reg_hl}
        with open(os.path.join(OUT, "index_regional.csv"), "w", newline="") as f:
            wr = csv.writer(f); wr.writerow(["week_start", "region", "events_13wk", "index_13wk", "vs_year_earlier_pct"])
            for i, wk in enumerate(weeks):
                if i < 12: continue
                for r in REGIONS + [UNKNOWN]:
                    s = R13[r][i]
                    ix = round(100 * s / RB[r], 1) if s >= MIN_CELL and RB[r] else ""
                    yoy = round((s / R13[r][i - 52] - 1) * 100, 1) if i >= 52 and R13[r][i - 52] >= MIN_CELL and s >= MIN_CELL else ""
                    wr.writerow([wk, r, s, ix, yoy])
        diff = []
        for i, wk in enumerate(weeks):
            if i < 64: continue
            up = flat = n = 0
            for r in REGIONS:
                a, b = R13[r][i], R13[r][i - 52]
                if a < MIN_CELL or b < MIN_CELL: continue
                n += 1; ch = a / b - 1
                if ch > 0.02: up += 1
                elif ch >= -0.02: flat += 1
            if n: diff.append((wk, round(100 * (up + 0.5 * flat) / n, 1), n))
        with open(os.path.join(OUT, "diffusion_regions.csv"), "w", newline="") as f:
            wr = csv.writer(f); wr.writerow(["week_start", "diffusion", "regions_counted"]); wr.writerows(diff)
        meta_idx = {"weights": {k: round(v, 4) for k, v in wts.items()},
                    "sd_13wk_log_change": {k: round(v, 4) for k, v in sds.items()},
                    "baseline_4wk_mean": {k: round(B4[k], 2) for k in COMPONENTS},
                    "petitions_baseline_4wk_mean": round(Bpet, 2)}
        latest = idx_rows[-1]
        summary = {"latest_week": latest["week_start"], "index": latest["index"], "provisional": latest["provisional"] == "1",
                   "change_vs_4wk_ago": round(latest["index"] - idx_rows[-5]["index"], 1),
                   "change_vs_year_ago": round(latest["index"] - idx_rows[-53]["index"], 1) if len(idx_rows) > 53 else None,
                   "components": {"administrations": latest["administrations"], "cvl": latest["cvl"],
                                  "winding_up_orders": latest["winding_up_orders"]},
                   "petitions_index": latest["petitions_index"], "equal_weight": latest["equal_weight"],
                   "plain_count": latest["plain_count"],
                   "holiday_affected": latest["holiday_affected"] == "1"}
        with open(os.path.join(OUT, "summary.json"), "w") as f: json.dump(summary, f, indent=1)

    # quality measures
    tot = len(notices)
    by = defaultdict(list)
    for n in notices: by[n["code"]].append(n)
    quality = {
        "notices": tot,
        "notices_by_code": {c: len(v) for c, v in sorted(by.items())},
        "notices_by_edition": dict(Counter(n["edition"] for n in notices)),
        "share_with_company_number": {c: round(sum(r["has_number"] == "1" for r in v) / len(v), 4) for c, v in by.items() if v},
        "share_located_by_map_point": round(sum(n["located"] == "1" for n in notices) / tot, 4) if tot else None,
        "share_region_unknown": round(sum(n["region"] == UNKNOWN for n in notices) / tot, 4) if tot else None,
        "dedup": {k: v for k, v in sorted(q.items())},
    }
    for comp in ("ADM", "CVL", "WUO", "PET"):
        nn, ee = q.get(f"{comp}_notices", 0), q.get(f"{comp}_events", 0)
        if nn: quality["dedup"][f"{comp}_notices_per_event"] = round(nn / ee, 3)
    meta = {
        "method_version": METHOD_VERSION,
        "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "first_week": weeks[0] if weeks else None, "last_complete_week": weeks[-1] if weeks else None,
        "baseline": {"from": BASELINE[0], "to": BASELINE[1], "meaning": "100 = average 4-week total in 2024-25 ('recent normal', not a long-run average)"},
        "components": COMPONENTS, "headline_components": HEADLINE, "gazette_codes": CODES,
        "index": meta_idx, "quality": quality, "fetch_totals": fetch_totals,
        "rules": {
            "unit": "One event per company per procedure (company number from the notice; company name where no number is shown). Repeat notices for the same company within 365 days (120 for CVLs, 180 for petitions) are not counted again.",
            "date_basis": "Week (Monday start) in which the first notice for the event was published in The Gazette. The free feed does not expose the appointment or order date.",
            "cvl": "Counted from liquidator appointment notices (2443), plus resolution notices (2441) only where they show a company number, one event per company. Companies with an administration in the previous 18 months are counted separately as administration-to-CVL moves, not as new CVLs.",
            "petitions": "Separate indicator from 4 April 2022, after Covid restrictions ended. The HMRC share of petitions is published only if HMRC can be detected in the free feed; at present the notice summary is truncated before the petitioner in most notices, so it is not shown.",
            "small_numbers": f"Regional figures use 13-week totals; cells with fewer than {MIN_CELL} events are not shown.",
            "location": f"Regions and constituencies come from the notice's map point (the registered office). A point shared by {OFFICE_MIN} or more different companies is an insolvency practitioner's, formation agent's or virtual office, not where the business traded, so those notices count towards their nation and the UK but not towards a region or constituency.",
            "weights": "Each headline component weighted by 1 / (standard deviation of its 13-week log change during 2024-25), normalised to sum to 1 (Conference Board method).",
            "provisional": "The latest 4 weeks are provisional.",
            "holidays": "Weeks whose four-week window includes Christmas/New Year (24 Dec - 14 Jan, allowing for the slow restart) or the Easter bank holidays are flagged holiday_affected: far fewer notices are published then, so the index dips for calendar reasons. Compare those weeks with the same weeks a year earlier. The index is not yet seasonally adjusted.",
            "restricted_period": "Winding-up petitions were restricted by law from spring 2020 to 31 March 2022 (Corporate Insolvency and Governance Act 2020 and follow-on regulations).",
        },
        "sources": ["Contains public sector information licensed under the Open Government Licence v3.0. Source: The Gazette (London, Edinburgh and Belfast editions).",
                    "postcodes.io (ONS Postcode Directory), Open Government Licence"],
        "not_official": "This is not an official statistic. The Insolvency Service's monthly figures are the authoritative measure.",
    }
    with open(os.path.join(OUT, "meta.json"), "w") as f: json.dump(meta, f, indent=1)
    log(f"published: {len(weeks)} weeks, {tot} notices, {len(events)} events")


def publish_constituencies(events, today):
    """Quarterly counts by Westminster constituency (July 2024 boundaries), from Q3 2024.
    Counts of public events only; no names. Quarters are dated by first notice.
    Members-only depth: written to the private cache, not the public site."""
    this_q = f"{today.year}-Q{(today.month - 1) // 3 + 1}"
    cnt = Counter()
    for comp, date, ed, reg, extra, *rest in events:
        con = rest[0] if rest else ""
        if not con or con == UNKNOWN or date[:7] < CONST_START: continue
        y, m = int(date[:4]), int(date[5:7])
        qtr = f"{y}-Q{(m - 1) // 3 + 1}"
        if qtr >= this_q: continue                      # complete quarters only
        group = {"ADM": "insolvencies", "ADM_TO_CVL": None, "CVL": "insolvencies", "WUO": "insolvencies",
                 "PET": "petitions"}.get(comp)
        if group: cnt[(qtr, con, reg, group)] += 1
        if comp in ("ADM", "CVL", "WUO"): cnt[(qtr, con, reg, comp)] += 1
    keys = sorted({(qt, con, reg) for qt, con, reg, _ in cnt})
    os.makedirs(PRIVATE, exist_ok=True)
    with open(os.path.join(PRIVATE, "constituency_quarterly.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["quarter", "constituency", "region", "insolvencies", "administrations", "cvl",
                     "winding_up_orders", "petitions"])
        for qt, con, reg in keys:
            wr.writerow([qt, con, reg] + [cnt[(qt, con, reg, g)] for g in
                                          ("insolvencies", "ADM", "CVL", "WUO", "petitions")])
    log(f"constituencies: {len({k[1] for k in keys})} seats, {len({k[0] for k in keys})} quarters")


def needs_constituency(path, tag):
    """Months cached before map points (and, from July 2024, constituencies) were recorded are
    fetched again once, only inside the Gazette's overnight window for bulk requests."""
    with open(path, newline="") as f:
        header = f.readline()
    if "pt" not in header.strip().split(","): return True
    return tag >= CONST_START and "constituency" not in header


def filter_office_points(notices):
    """Gazette map points are the company's registered office, which after an insolvency is usually
    moved to the insolvency practitioner's office (or was a formation agent / virtual office). A point
    shared by OFFICE_MIN or more different companies is treated as such an office: those notices keep
    their nation but lose region and constituency, so local figures reflect where companies traded."""
    comp = defaultdict(set)
    for n in notices:
        if n.get("pt"): comp[n["pt"]].add(n["key"])
    office = {pt for pt, ks in comp.items() if len(ks) >= OFFICE_MIN}
    moved = 0
    for n in notices:
        if n.get("pt") in office:
            n["region"] = EDITIONS[n["edition"]] if n["edition"] in ("Edinburgh", "Belfast") else UNKNOWN
            n["constituency"] = UNKNOWN; n["located"] = "0"; moved += 1
    return {"office_points": len(office), "notices_at_office_points": moved,
            "share_at_office_points": round(moved / len(notices), 4) if notices else None,
            "notices_without_point_field": sum(1 for n in notices if "pt" not in n or n["pt"] is None)}


# ---------------------------------------------------------------- main
def months(start, end):
    x = start.replace(day=1)
    while x <= end:
        nxt = (x.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        yield x, min(nxt - dt.timedelta(days=1), end); x = nxt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--max-minutes", type=float, default=300)
    ap.add_argument("--refresh-days", type=int, default=45)
    a = ap.parse_args()
    today = dt.date.today()
    start, end = d(a.start), (d(a.end) if a.end else today)
    os.makedirs(NOTICE_CACHE, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    t0, geo, complete, fetch_totals = time.time(), load_geo(), True, {}
    for ms, me in months(start, end):
        tag = f"{ms:%Y-%m}"
        p = os.path.join(NOTICE_CACHE, f"{tag}.csv")
        night = dt.datetime.now(dt.timezone.utc).hour >= 21 or dt.datetime.now(dt.timezone.utc).hour < 7
        if os.path.exists(p) and (today - me).days > a.refresh_days and not (night and needs_constituency(p, tag)):
            tp = os.path.join(NOTICE_CACHE, f"{tag}.totals.json")
            if os.path.exists(tp): fetch_totals[tag] = json.load(open(tp))
            continue
        if (time.time() - t0) / 60 > a.max_minutes:
            log(f"time budget reached before {tag}; continuing next run"); complete = False; break
        log(f"month {tag}")
        rows, totals, geo = fetch_month(ms, me, geo)
        write_notice_cache(tag, rows, totals); save_geo(geo); fetch_totals[tag] = totals
    old_public = os.path.join(OUT, "constituency_quarterly.csv")   # constituency figures are members-only
    if os.path.exists(old_public): os.remove(old_public)
    notices = load_notices()
    office_stats = filter_office_points(notices)
    log(f"office addresses: {office_stats}")
    events, q = build_events(notices)
    q["office_" + "points"] = office_stats["office_points"]; q["office_notices"] = office_stats["notices_at_office_points"]
    if complete:
        publish(notices, events, q, today, fetch_totals)
        pending = [f[:7] for f in os.listdir(NOTICE_CACHE) if f.endswith(".csv")
                   and needs_constituency(os.path.join(NOTICE_CACHE, f), f[:7])]
        if pending:
            log(f"constituencies: {len(pending)} months still to be refetched overnight; table not published yet")
            stale = os.path.join(PRIVATE, "constituency_quarterly.csv")
            if os.path.exists(stale): os.remove(stale)
        else:
            publish_constituencies(events, today)
    else:
        log("backfill incomplete: published files left unchanged until the history is complete")
    with open(os.path.join(OUT, "backfill_status.json"), "w") as f:
        json.dump({"method_version": METHOD_VERSION, "complete": complete,
                   "months_cached": len([x for x in os.listdir(NOTICE_CACHE) if x.endswith('.csv')]),
                   "checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}, f)


if __name__ == "__main__":
    main()
