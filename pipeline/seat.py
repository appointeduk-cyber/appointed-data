"""State of the Seat: one Westminster constituency, every month.

Builds a members-only data pack for one seat from official sources:
  economy   - insolvencies and winding-up petitions (The Gazette, our own build cache)
  jobs      - claimant count (ONS via Nomis)
  crime     - street-level crime (data.police.uk), counted inside the constituency boundary
  housing   - UK House Price Index for the local authority (HM Land Registry)

Every figure carries its source, period and fetch time. Each source is checked on its own; a
source that fails or looks wrong is marked unavailable rather than guessed. Output goes to the
private cache (.cache/private/seats/), never to the public site.

  python pipeline/seat.py --seat "Kingston and Surbiton" --la kingston-upon-thames
"""
import argparse, csv, datetime as dt, html, io, json, os, re, statistics, sys, time
import urllib.parse, urllib.request
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import build  # noqa: E402  (reuses the notice cache and event rules, so seat figures match the index)

UA = "Appointed data (appointed.news; appointeduk@gmail.com)"
OUT = os.path.join(build.PRIVATE, "seats")
BOUNDARY = ("https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "Westminster_Parliamentary_Constituencies_July_2024_Boundaries_UK_BGC/FeatureServer/0/query")
POLICE = "https://data.police.uk/api"
NOMIS = "https://www.nomisweb.co.uk/api/v01/dataset/NM_162_1"
HPI_SPARQL = "https://landregistry.data.gov.uk/landregistry/query"
NOW = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def log(*a): print(*a, flush=True)


def get(url, data=None, accept="application/json", tries=4):
    headers = {"User-Agent": UA, "Accept": accept}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    wait = 5
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=90) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            log(f"  {url[:90]} -> {e!r} ({i + 1}/{tries})")
            if code in (400, 401, 403, 404): raise
            time.sleep(wait); wait *= 2
    raise RuntimeError(f"giving up on {url}")


def section(name, source, url):
    return {"name": name, "source": source, "source_url": url, "fetched_utc": NOW, "status": "ok", "checks": []}


def fail(sec, why):
    sec["status"] = "unavailable"; sec["reason"] = why; log(f"  {sec['name']}: UNAVAILABLE - {why}")
    return sec


def check(sec, ok, text):
    sec["checks"].append({"ok": bool(ok), "check": text})
    if not ok: log(f"  {sec['name']}: check failed - {text}")
    return ok


# ---------------------------------------------------------------- boundary
def boundary(seat):
    q = {"where": f"PCON24NM='{seat}'", "outFields": "PCON24CD,PCON24NM", "outSR": "4326", "f": "geojson"}
    doc = json.loads(get(BOUNDARY + "?" + urllib.parse.urlencode(q)))
    feats = doc.get("features") or []
    if not feats: raise RuntimeError(f"no boundary found for {seat!r}")
    g, props = feats[0]["geometry"], feats[0]["properties"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    rings = [p[0] for p in polys]
    return props.get("PCON24CD"), rings


def ring_area(r):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]))) / 2


def simplify(ring, n=180):
    step = max(1, len(ring) // n)
    pts = ring[::step]
    return pts if pts[-1] == ring[-1] else pts + [ring[-1]]


# ---------------------------------------------------------------- economy (our Gazette cache)
def economy(seat, today):
    sec = section("economy", "The Gazette (official public record), counted by Appointed",
                  "https://www.thegazette.co.uk/insolvency")
    notices = build.load_notices()
    if not notices: return fail(sec, "notice cache is empty")
    build.filter_office_points(notices)
    events, _ = build.build_events(notices)
    months_missing = sorted({n["date"][:7] for n in notices
                             if n["date"][:7] >= build.CONST_START and "constituency" not in n})
    cnt, names = Counter(), []
    for comp, date, ed, reg, extra, *rest in events:
        con = rest[0] if rest else ""
        if con != seat: continue
        cnt[(date[:7], comp)] += 1
    # named list: the seat's notices over the last 13 months (private; the notice id lets us fetch the name)
    since = (today.replace(day=1) - dt.timedelta(days=380)).isoformat()[:7]
    label = {"2410": "Administration", "2443": "Creditors' voluntary liquidation", "2441": "Creditors' voluntary liquidation",
             "2452": "Winding-up order", "2450": "Winding-up petition (not an insolvency)",
             "2451": "Winding-up petition (not an insolvency)"}
    seen = set()
    for n in sorted(notices, key=lambda r: r["date"], reverse=True):
        if n.get("constituency") != seat or n["code"] not in label or n["date"][:7] < since: continue
        k = (n["key"], label[n["code"]])
        if k in seen: continue
        seen.add(k)
        names.append({"date": n["date"], "type": label[n["code"]], "notice_id": n["id"],
                      "notice_url": f"https://www.thegazette.co.uk/notice/{n['id']}", "company_key": n["key"]})
    for row in names[:80]:
        k = row.pop("company_key")
        if k.startswith("N:"):
            row["company"] = k[2:].title(); continue
        num = k[2:]; row["company_number"] = num
        url = f"https://find-and-update.company-information.service.gov.uk/company/{num}"
        row["companies_house_url"] = url
        try:
            page = get(url, accept="text/html")
            m = (re.search(r'id="company-name"[^>]*>\s*([^<]+?)\s*<', page)
                 or re.search(r"<title>\s*(.+?)\s+overview", page, re.S | re.I))
            row["company"] = html.unescape(m.group(1)).strip() if m else ""
            if not row["company"]: log(f"  no name found on Companies House page for {num}: {page[:300]!r}")
            row["sic"] = [html.unescape(x).strip() for x in re.findall(r'<span id="sic\d+">\s*([^<]+?)\s*</span>', page)]
            m = re.search(r'id="company-creation-date">\s*([^<]+?)\s*<', page)
            row["incorporated"] = m.group(1) if m else ""
            m = re.search(r'id="company-status">\s*([^<]+?)\s*<', page)
            row["status_at_companies_house"] = m.group(1) if m else ""
            time.sleep(0.6)
        except Exception as e:  # noqa: BLE001
            row["company"] = ""; log(f"  Companies House lookup failed {num}: {e!r}")
    def norm(x): return re.sub(r"\b(LIMITED|LTD|PLC|LLP)\b|[^A-Z0-9]", "", (x or "").upper())
    keep, seen_names = [], set()
    for row in sorted(names, key=lambda r: ("company_number" not in r, r["date"])):   # numbered rows first
        k = (norm(row.get("company")), row["type"])
        if k[0] and k in seen_names: continue
        seen_names.add(k); keep.append(row)
    names = sorted(keep, key=lambda r: r["date"], reverse=True)
    months = sorted({m for m, _ in cnt})
    sec["monthly"] = [{"month": m,
                       "insolvencies": cnt[(m, "ADM")] + cnt[(m, "CVL")] + cnt[(m, "WUO")],
                       "administrations": cnt[(m, "ADM")], "cvl": cnt[(m, "CVL")],
                       "winding_up_orders": cnt[(m, "WUO")], "petitions": cnt[(m, "PET")]} for m in months]
    sec["named"] = names
    sec["months_without_constituency"] = months_missing
    check(sec, not months_missing, "every month since July 2024 has constituency locations "
          f"({len(months_missing)} still to be refetched overnight)")
    check(sec, len(months) >= 6, f"at least six months with events ({len(months)})")
    sec["note"] = ("Located by the company's registered office on the Gazette map point, after removing insolvency "
                   "firms' office addresses. A petition is a creditor's application to court, not an insolvency.")
    return sec


# ---------------------------------------------------------------- crime
def crime(rings):
    sec = section("crime", "data.police.uk (Home Office), street-level crime", "https://data.police.uk/")
    try:
        dates = sorted(x["date"] for x in json.loads(get(POLICE + "/crimes-street-dates")))
    except Exception as e:  # noqa: BLE001
        return fail(sec, f"could not read the list of months: {e!r}")
    latest = dates[-1]
    want = dates[-25:]   # two years plus one month: enough for year-on-year on every recent month
    ring = max(rings, key=ring_area)
    poly = ":".join(f"{lat:.5f},{lon:.5f}" for lon, lat in simplify(ring))
    sec["boundary_points_used"] = poly.count(":") + 1
    rows = []
    for m in want:
        try:
            data = json.loads(get(POLICE + "/crimes-street/all-crime", data={"poly": poly, "date": m}))
        except Exception as e:  # noqa: BLE001
            log(f"  crime {m}: {e!r}"); rows.append({"month": m, "total": None}); continue
        c = Counter(x.get("category", "other") for x in data)
        rows.append({"month": m, "total": len(data), "by_category": dict(c.most_common())})
        time.sleep(0.5)
    sec["monthly"] = rows; sec["latest_month"] = latest
    tot = [r["total"] for r in rows if r["total"] is not None]
    if not tot: return fail(sec, "no months returned")
    med = statistics.median(tot)
    check(sec, rows[-1]["total"] is not None, f"latest month ({latest}) returned")
    check(sec, all(0.5 * med <= t <= 2 * med for t in tot), "every month within half to double the two-year median")
    check(sec, max(tot) < 9500, "no month near the 10,000-record limit of the police API")
    sec["note"] = ("Crime locations are moved by the police to the nearest anonymous map point, so counts near the "
                   "boundary are approximate. Some forces publish late or revise earlier months.")
    return sec


# ---------------------------------------------------------------- claimant count
def nomis_codes(seat):
    types = json.loads(get(NOMIS + "/geography/TYPE.def.sdmx.json"))
    codes = types["structure"]["codelists"]["codelist"][0]["code"]
    cand = [c for c in codes if "constituenc" in c["description"]["value"].lower() and "2024" in c["description"]["value"]]
    if not cand: raise RuntimeError("no 2024 constituency geography type on Nomis: " +
                                    "; ".join(c["description"]["value"] for c in codes)[:600])
    t = cand[0]["value"]
    geos = json.loads(get(f"{NOMIS}/geography/{t}.def.sdmx.json"))["structure"]["codelists"]["codelist"][0]["code"]
    hit = [g for g in geos if g["description"]["value"].lower() == seat.lower()]
    if not hit: raise RuntimeError(f"{seat} not found in Nomis type {t}")
    return t, cand[0]["description"]["value"], hit[0]["value"]


def claimants(seat):
    sec = section("jobs", "Office for National Statistics, Claimant Count (via Nomis)",
                  "https://www.nomisweb.co.uk/datasets/ucjsa")
    try:
        t, tname, gid = nomis_codes(seat)
    except Exception as e:  # noqa: BLE001
        return fail(sec, f"could not find the constituency on Nomis: {e!r}")
    sec["nomis_geography"] = {"type": t, "type_name": tname, "id": gid}
    out = {}
    for label, geo in (("seat", gid), ("uk", "2092957697")):
        q = {"geography": geo, "date": "latestMINUS24-latest", "gender": "0", "age": "0", "measure": "1,2",
             "measures": "20100", "select": "date,date_name,geography_name,measure_name,obs_value"}
        try:
            txt = get(NOMIS + ".data.csv?" + urllib.parse.urlencode(q), accept="text/csv")
        except Exception as e:  # noqa: BLE001
            if label == "seat": return fail(sec, f"data request failed: {e!r}")
            continue
        rows = list(csv.DictReader(io.StringIO(txt)))
        series = defaultdict(dict)
        for r in rows:
            r = {k.lower(): v for k, v in r.items()}
            kind = "count" if "count" in r["measure_name"].lower() else "rate"
            try: series[r["date"]][kind] = float(r["obs_value"])
            except ValueError: pass
        out[label] = [{"month": k, **v} for k, v in sorted(series.items())]
    sec["monthly"] = out.get("seat", []); sec["uk"] = out.get("uk", [])
    if not sec["monthly"]: return fail(sec, "no rows returned")
    check(sec, all(r.get("count", 0) >= 0 for r in sec["monthly"]), "counts are not negative")
    check(sec, len(sec["monthly"]) >= 13, f"at least 13 months for year-on-year ({len(sec['monthly'])})")
    sec["note"] = ("People claiming unemployment-related benefits (Universal Credit searching for work, plus JSA). "
                   "The rate is the share of residents aged 16 to 64. Latest month is provisional.")
    return sec


# ---------------------------------------------------------------- house prices
def housing(la):
    sec = section("housing", "HM Land Registry, UK House Price Index", "https://landregistry.data.gov.uk/app/ukhpi")
    q = f"""PREFIX ukhpi: <http://landregistry.data.gov.uk/def/ukhpi/>
SELECT ?month ?avg ?annual ?vol WHERE {{
  ?r ukhpi:refRegion <http://landregistry.data.gov.uk/id/region/{la}> ; ukhpi:refMonth ?month ; ukhpi:averagePrice ?avg .
  OPTIONAL {{ ?r ukhpi:percentageAnnualChange ?annual }} OPTIONAL {{ ?r ukhpi:salesVolume ?vol }}
}} ORDER BY DESC(?month) LIMIT 30"""
    rows = []
    try:
        doc = json.loads(get(HPI_SPARQL, data={"query": q}, accept="application/sparql-results+json"))
        for b in doc.get("results", {}).get("bindings", []):
            def v(k): return b[k]["value"] if k in b else None
            rows.append({"month": v("month")[:7], "average_price": float(v("avg")),
                         "annual_change_pct": float(v("annual")) if v("annual") else None,
                         "sales_volume": int(float(v("vol"))) if v("vol") else None})
        sec["method"] = "sparql"
    except Exception as e:  # noqa: BLE001
        log(f"  housing: SPARQL failed ({e!r}); trying the month-by-month API")
        m0 = dt.date.today().replace(day=1)
        for i in range(1, 30):
            y, mo = divmod(m0.year * 12 + m0.month - 1 - i, 12); tag = f"{y}-{mo + 1:02d}"
            url = f"https://landregistry.data.gov.uk/data/ukhpi/region/{la}/month/{tag}.json"
            try:
                doc = json.loads(get(url, tries=2))
            except Exception as e2:  # noqa: BLE001
                log(f"  housing {tag}: {e2!r}"); continue
            t = doc.get("result", {}).get("primaryTopic", {})
            if "averagePrice" not in t: continue
            def num(x):
                x = x[0] if isinstance(x, list) else x
                return float(x) if x not in (None, "") else None
            rows.append({"month": tag, "average_price": num(t.get("averagePrice")),
                         "annual_change_pct": num(t.get("percentageAnnualChange")),
                         "sales_volume": int(num(t.get("salesVolume"))) if t.get("salesVolume") not in (None, "") else None})
            if len(rows) >= 25: break
        sec["method"] = "linked-data"
    if not rows:
        log("  housing: trying the monthly UK HPI full file")
        m0 = dt.date.today().replace(day=1)
        name = la.replace("-", " ").lower()
        for i in range(1, 6):
            y, mo = divmod(m0.year * 12 + m0.month - 1 - i, 12); tag = f"{y}-{mo + 1:02d}"
            url = ("https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/"
                   f"UK-HPI-full-file-{tag}.csv")
            try:
                txt = get(url, accept="text/csv", tries=2)
            except Exception as e2:  # noqa: BLE001
                log(f"  HPI file {tag}: {e2!r}"); continue
            for r in csv.DictReader(io.StringIO(txt)):
                if r.get("RegionName", "").lower() != name: continue
                dd, mm, yy = r["Date"].split("/")
                def f(k):
                    try: return float(r.get(k) or "")
                    except ValueError: return None
                rows.append({"month": f"{yy}-{mm}", "average_price": f("AveragePrice"),
                             "annual_change_pct": f("12m%Change"),
                             "sales_volume": int(f("SalesVolume")) if f("SalesVolume") is not None else None})
            rows = [r for r in rows if r["month"] >= f"{m0.year - 3}"]
            sec["method"] = "full-file"; sec["source_file"] = url
            break
    rows.sort(key=lambda r: r["month"])
    if not rows: return fail(sec, f"no rows for region '{la}'")
    sec["monthly"] = rows; sec["area"] = la
    latest = dt.date.fromisoformat(rows[-1]["month"] + "-01")
    check(sec, (dt.date.today() - latest).days < 200, f"latest month ({rows[-1]['month']}) is recent")
    check(sec, all(50_000 < r["average_price"] < 5_000_000 for r in rows), "average prices in a believable range")
    sec["note"] = ("Covers the whole local authority, not just the constituency. The index runs about two months "
                   "behind, and the latest months are revised as more sales are registered.")
    return sec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seat", required=True)
    ap.add_argument("--la", required=True, help="Land Registry region slug, e.g. kingston-upon-thames")
    a = ap.parse_args()
    today = dt.date.today()
    pack = {"seat": a.seat, "built_utc": NOW, "boundaries": "Westminster constituencies, July 2024", "sections": {}}
    try:
        code, rings = boundary(a.seat); pack["seat_code"] = code
        log(f"boundary: {code}, {len(rings)} part(s), largest {len(max(rings, key=ring_area))} points")
    except Exception as e:  # noqa: BLE001
        log(f"boundary failed: {e!r}"); rings = None
    for name, fn in (("economy", lambda: economy(a.seat, today)),
                     ("jobs", lambda: claimants(a.seat)),
                     ("crime", lambda: crime(rings) if rings else fail(section("crime", "data.police.uk", POLICE), "no boundary")),
                     ("housing", lambda: housing(a.la))):
        log(f"section {name}")
        try: pack["sections"][name] = fn()
        except Exception as e:  # noqa: BLE001
            pack["sections"][name] = fail(section(name, "", ""), f"unexpected error: {e!r}")
    os.makedirs(OUT, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", a.seat.lower()).strip("-")
    p = os.path.join(OUT, f"{slug}.json")
    with open(p, "w") as f: json.dump(pack, f, indent=1)
    for k, s in pack["sections"].items():
        log(f"{k}: {s['status']}; checks passed {sum(c['ok'] for c in s['checks'])}/{len(s['checks'])}")
    log(f"wrote {p}")


if __name__ == "__main__":
    main()
