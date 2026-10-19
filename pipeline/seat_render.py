"""Render a State of the Seat pack (JSON from seat.py) as one self-contained HTML page.

  python pipeline/seat_render.py PACK.json OUT.html [--sample]

The page is members-only: it lists named companies, so it is never written under docs/.
"""
import html, json, sys, datetime as dt

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
CRIME_LABEL = {"violent-crime": "Violence and sexual offences", "anti-social-behaviour": "Anti-social behaviour",
               "shoplifting": "Shoplifting", "public-order": "Public order", "other-theft": "Other theft",
               "vehicle-crime": "Vehicle crime", "drugs": "Drugs", "burglary": "Burglary",
               "theft-from-the-person": "Theft from the person", "bicycle-theft": "Bicycle theft",
               "robbery": "Robbery", "criminal-damage-arson": "Criminal damage and arson",
               "possession-of-weapons": "Possession of weapons", "other-crime": "Other crime"}
SIC_GROUP = [("56", "Hospitality (restaurants, pubs, takeaways)"), ("41", "Construction"), ("42", "Construction"),
             ("43", "Construction"), ("68", "Property"), ("62", "Tech and IT"), ("63", "Tech and IT"),
             ("47", "Retail"), ("46", "Wholesale"), ("86", "Health and care"), ("87", "Health and care"),
             ("88", "Health and care"), ("85", "Education"), ("96", "Personal services"),
             ("69", "Professional services"), ("70", "Professional services"), ("82", "Business support"),
             ("78", "Business support"), ("81", "Business support")]


AREA = {"kingston-upon-thames": "Kingston upon Thames", "richmond-upon-thames": "Richmond upon Thames"}


def esc(x): return html.escape(str(x if x is not None else ""))
def mlabel(m, year=True): y, mo = m.split("-"); return f"{MONTHS[int(mo) - 1]}{' ' + y if year else ''}"
def pct(a, b): return None if not b else (a - b) / b * 100
def sp(x, d=0): return "–" if x is None else f"{'+' if x > 0 else ''}{x:.{d}f}%"
def sic_group(sic):
    if not sic: return "Not recorded"
    for pre, name in SIC_GROUP:
        if sic[0].startswith(pre): return name
    return "Other"
def sector_short(sic):
    if not sic: return ""
    s = sic[0].split(" - ", 1)[-1]
    return s if len(s) < 48 else s[:45] + "…"


def line_svg(series, w=760, h=230, fmt=lambda v: f"{v:,.0f}", ymin=None, ymax=None, note=None):
    """series: list of (label, colour_var, [(month, value)...], dashed)"""
    pad_l, pad_r, pad_t, pad_b = 54, 14, 14, 30
    months = sorted({m for _, _, pts, _ in series for m, _ in pts})
    vals = [v for _, _, pts, _ in series for _, v in pts if v is not None]
    lo = min(vals) if ymin is None else ymin; hi = max(vals) if ymax is None else ymax
    span = (hi - lo) or 1
    raw = span / 4; mag = 10 ** __import__("math").floor(__import__("math").log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    lo = __import__("math").floor(lo / step) * step; hi = __import__("math").ceil(hi / step) * step
    nt = round((hi - lo) / step)
    X = lambda i: pad_l + i * (w - pad_l - pad_r) / max(1, len(months) - 1)
    Y = lambda v: pad_t + (hi - v) * (h - pad_t - pad_b) / (hi - lo)
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img">']
    for k in range(nt + 1):
        v = lo + step * k; y = Y(v)
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{y:.1f}" y2="{y:.1f}" stroke="var(--rule)"/>'
                   f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="var(--muted)">{esc(fmt(v))}</text>')
    for i, m in enumerate(months):
        if m.endswith("-01") or i == 0 or i == len(months) - 1:
            out.append(f'<text x="{X(i):.1f}" y="{h - 8}" text-anchor="middle" font-size="11" fill="var(--muted)">{mlabel(m)}</text>')
    idx = {m: i for i, m in enumerate(months)}
    for label, col, pts, dashed in series:
        d = " ".join(f"{'M' if j == 0 else 'L'}{X(idx[m]):.1f},{Y(v):.1f}" for j, (m, v) in enumerate(pts) if v is not None)
        out.append(f'<path d="{d}" fill="none" stroke="var({col})" stroke-width="{2 if dashed else 2.6}"'
                   f'{" stroke-dasharray=\"5 4\"" if dashed else ""} stroke-linejoin="round"/>')
        m, v = pts[-1]
        out.append(f'<circle cx="{X(idx[m]):.1f}" cy="{Y(v):.1f}" r="3.5" fill="var({col})"/>')
    out.append("</svg>")
    return "".join(out)


def bars_svg(rows, gap_months, w=760, h=210):
    pad_l, pad_r, pad_t, pad_b = 30, 10, 12, 30
    n = len(rows); bw = (w - pad_l - pad_r) / n
    hi = max(max(r["insolvencies"], r["petitions"]) for r in rows) or 1
    Y = lambda v: pad_t + (hi - v) * (h - pad_t - pad_b) / hi
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img">']
    for k in range(0, hi + 1, max(1, hi // 4)):
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{Y(k):.1f}" y2="{Y(k):.1f}" stroke="var(--rule)"/>'
                   f'<text x="{pad_l - 6}" y="{Y(k) + 4:.1f}" text-anchor="end" font-size="11" fill="var(--muted)">{k}</text>')
    for i, r in enumerate(rows):
        x = pad_l + i * bw
        if r["month"] in gap_months:
            out.append(f'<rect x="{x:.1f}" y="{pad_t}" width="{bw:.1f}" height="{h - pad_t - pad_b}" fill="var(--warn-bg)"/>')
            out.append(f'<text x="{x + bw / 2:.1f}" y="{pad_t + 14}" text-anchor="middle" font-size="10" fill="var(--warn-ink)">?</text>')
        else:
            b1 = bw * .42
            out.append(f'<rect x="{x + bw * .1:.1f}" y="{Y(r["insolvencies"]):.1f}" width="{b1:.1f}" height="{Y(0) - Y(r["insolvencies"]):.1f}" fill="var(--bar)" rx="1.5"/>')
            out.append(f'<rect x="{x + bw * .1 + b1:.1f}" y="{Y(r["petitions"]):.1f}" width="{b1 * .8:.1f}" height="{Y(0) - Y(r["petitions"]):.1f}" fill="var(--bar-3)" rx="1.5"/>')
        if r["month"].endswith("-01") or i in (0, n - 1):
            out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 8}" text-anchor="middle" font-size="11" fill="var(--muted)">{mlabel(r["month"])}</text>')
    out.append("</svg>")
    return "".join(out)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    sample = "--sample" in sys.argv
    p = json.load(open(src))
    S = p["sections"]; seat = p["seat"]
    eco, jobs, crime, house = S["economy"], S["jobs"], S["crime"], S["housing"]
    built = dt.datetime.fromisoformat(p["built_utc"]).strftime("%-d %B %Y")
    edition = dt.date.fromisoformat(p["built_utc"][:10]).strftime("%B %Y")

    # ---- crime
    cm = [r for r in crime["monthly"] if r["total"] is not None]
    last, prev = cm[-1], next((r for r in cm if r["month"] == f"{int(cm[-1]['month'][:4]) - 1}{cm[-1]['month'][4:]}"), None)
    c12, p12 = cm[-12:], cm[-24:-12]
    def tot(rows, cat=None): return sum((r["by_category"].get(cat, 0) if cat else r["total"]) for r in rows)
    cats = sorted(CRIME_LABEL, key=lambda c: -tot(c12, c))
    crime_rows = "".join(
        f'<tr><td>{CRIME_LABEL[c]}</td><td class="r num">{tot(c12, c):,}</td><td class="r num">{tot(p12, c):,}</td>'
        f'<td class="r num {"up" if (pct(tot(c12, c), tot(p12, c)) or 0) > 0 else "down"}">{sp(pct(tot(c12, c), tot(p12, c)))}</td></tr>'
        for c in cats[:8])
    crime_yoy_m = pct(last["total"], prev["total"]) if prev else None
    crime_yoy_12 = pct(tot(c12), tot(p12))
    vio = pct(tot(c12, "violent-crime"), tot(p12, "violent-crime"))
    bur = pct(tot(c12, "burglary"), tot(p12, "burglary"))

    # ---- jobs
    jm, uk = jobs["monthly"], {r["month"]: r for r in jobs["uk"]}
    jl = jm[-1]; jp = next((r for r in jm if r["month"] == f"{int(jl['month'][:4]) - 1}{jl['month'][4:]}"), None)
    ukl = uk.get(jl["month"]); ukp = uk.get(jp["month"]) if jp else None
    j_yoy, uk_yoy = pct(jl["count"], jp["count"]) if jp else None, pct(ukl["count"], ukp["count"]) if ukl and ukp else None

    # ---- housing
    hm = house.get("monthly", []); hl = hm[-1] if hm else None

    # ---- economy
    gap = set(eco.get("months_without_constituency", []))
    em = {r["month"]: r for r in eco["monthly"]}
    start = "2024-07"; cur = dt.date.fromisoformat(p["built_utc"][:10]).replace(day=1)
    allm, y, mo = [], 2024, 7
    while f"{y}-{mo:02d}" < f"{cur:%Y-%m}":
        allm.append(f"{y}-{mo:02d}"); mo += 1
        if mo == 13: y, mo = y + 1, 1
    erows = [em.get(m, {"month": m, "insolvencies": 0, "petitions": 0}) for m in allm]
    latest_full = allm[-1]
    el = em.get(latest_full, {"insolvencies": 0, "petitions": 0, "administrations": 0, "cvl": 0, "winding_up_orders": 0})
    import re
    for r in eco["named"]:
        if r.get("company"): r["company"] = re.sub(r"(?i)&apos;?\s?", "'", r["company"]).replace("'S ", "'s ")
    def nm(x): return re.sub(r"\b(LIMITED|LTD|PLC|LLP)\b|[^A-Z0-9]", "", (x or "").upper())
    numbered = [(nm(r.get("company")), r["type"]) for r in eco["named"] if r.get("company_number")]
    eco["named"] = [r for r in eco["named"] if r.get("company_number") or not any(
        t == r["type"] and n.startswith(nm(r.get("company"))) for n, t in numbered)]
    ins_named = [r for r in eco["named"] if "petition" not in r["type"]]
    pet_named = [r for r in eco["named"] if "petition" in r["type"]]
    groups = {}
    for r in ins_named: groups[sic_group(r.get("sic"))] = groups.get(sic_group(r.get("sic")), 0) + 1
    top_groups = sorted(((n, g) for g, n in groups.items() if g not in ("Not recorded", "Other")), reverse=True)[:5]
    gmax = top_groups[0][0] if top_groups else 1

    def named_table(rows, limit):
        out = []
        for r in rows[:limit]:
            link = r.get("companies_house_url") or r["notice_url"]
            out.append(f'<tr><td class="num">{dt.date.fromisoformat(r["date"]).strftime("%-d %b %Y")}</td>'
                       f'<td><a href="{esc(link)}">{esc(r.get("company") or "Name not yet matched")}</a></td>'
                       f'<td>{esc(r["type"].replace(" (not an insolvency)", ""))}</td>'
                       f'<td>{esc(sector_short(r.get("sic")))}</td>'
                       f'<td class="num">{esc((r.get("incorporated") or "")[-4:])}</td>'
                       f'<td><a href="{esc(r["notice_url"])}">Notice</a></td></tr>')
        return "".join(out)

    checks = []
    for name in ("economy", "jobs", "crime", "housing"):
        s = S[name]
        for c in s.get("checks", []):
            checks.append(f'<li><span class="{"ok" if c["ok"] else "no"}">{"✓" if c["ok"] else "!"}</span>'
                          f'<b>{name.title()}</b> {esc(c["check"])}</li>')

    gap_txt = ", ".join(mlabel(m) for m in sorted(gap))
    banner = (f'<div class="draft"><b>Sample for review. Not for sending.</b>Real figures from official sources, built '
              f'automatically on {built}. {"Business figures for " + gap_txt + " are being re-checked overnight and are left blank rather than guessed." if gap else ""}</div>') if sample else ""

    page = f"""<title>State of the Seat: {esc(seat)}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root{{
  --bg:#f6f7f9; --paper:#ffffff; --ink:#0a1014; --ink-2:#3a4552; --muted:#6b7480; --rule:#dde1e6;
  --blue:#1b82fd; --blue-ink:#1667c9; --hl:#d0e6fd; --ref:#8a94a0; --warn-bg:#fff4e0; --warn-ink:#7a4b00; --warn-rule:#f0d7a8;
  --bar:#1b82fd; --bar-2:#9ec5f4; --bar-3:#f2a33a; --up:#b4362f; --down:#1e7a4f;
  --f-body:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{
  --bg:#0f1418; --paper:#161d23; --ink:#eef2f5; --ink-2:#c3ccd5; --muted:#8f9aa6; --rule:#2a333c;
  --blue:#4c9dff; --blue-ink:#7db6ff; --hl:#18375c; --ref:#7b8794; --warn-bg:#2b2111; --warn-ink:#f3c97a; --warn-rule:#4a3a1c;
  --bar:#4c9dff; --bar-2:#2a5a93; --bar-3:#e0973a; --up:#f08a82; --down:#6fd1a1; color-scheme:dark}}}}
:root[data-theme="dark"]{{
  --bg:#0f1418; --paper:#161d23; --ink:#eef2f5; --ink-2:#c3ccd5; --muted:#8f9aa6; --rule:#2a333c;
  --blue:#4c9dff; --blue-ink:#7db6ff; --hl:#18375c; --ref:#7b8794; --warn-bg:#2b2111; --warn-ink:#f3c97a; --warn-rule:#4a3a1c;
  --bar:#4c9dff; --bar-2:#2a5a93; --bar-3:#e0973a; --up:#f08a82; --down:#6fd1a1; color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15.5px/1.6 var(--f-body);padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:28px 56px}}
a{{color:var(--blue-ink)}}
.wrap{{max-width:840px;margin:0 auto;display:grid;gap:18px}}
.num{{font-variant-numeric:tabular-nums}}
h1,h2,h3{{letter-spacing:-.02em;line-height:1.15;margin:0;text-wrap:balance}}
.kicker{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--blue-ink);font-weight:700;margin:0}}
.small{{font-size:13px;color:var(--muted);margin:0}}
header{{display:grid;gap:8px;padding-block:6px 4px}}
header h1{{font-size:clamp(30px,5vw,44px);font-weight:900}}
header .seat{{font-size:clamp(20px,3vw,26px);font-weight:800;color:var(--ink-2)}}
.draft{{background:var(--warn-bg);color:var(--warn-ink);border:1px solid var(--warn-rule);border-radius:10px;padding:12px 16px;font-size:14px}}
.draft b{{display:block;margin-bottom:2px}}
section{{background:var(--paper);border:1px solid var(--rule);border-radius:12px;padding:20px 22px;display:grid;gap:12px;min-width:0}}
section h2{{font-size:19px;font-weight:800}}
section p{{margin:0}}
.lead{{display:grid;gap:10px;margin:0;padding:0;list-style:none}}
.lead li{{display:grid;grid-template-columns:92px 1fr;gap:12px;align-items:baseline}}
.lead .tag{{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:var(--blue-ink)}}
.stats{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}
@media(max-width:620px){{.stats{{grid-template-columns:1fr}} .lead li{{grid-template-columns:1fr;gap:0}}}}
.stat{{border-top:3px solid var(--blue);padding-top:10px}}
.stat .n{{font-size:32px;font-weight:900;letter-spacing:-.03em;line-height:1}}
.stat .l{{font-size:13.5px;color:var(--ink-2);margin-top:6px}}
.chart{{width:100%;height:auto;display:block}}
.legend{{display:flex;flex-wrap:wrap;gap:16px;font-size:13px;color:var(--ink-2)}}
.legend i{{display:inline-block;width:14px;height:10px;border-radius:2px;margin-right:6px;vertical-align:middle}}
.legend i.dash{{height:0;border-top:2px dashed var(--ref);border-radius:0}}
.tbl{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}}
td{{white-space:nowrap}} td:nth-child(2),td:nth-child(4){{white-space:normal;min-width:150px}} td:nth-child(2){{min-width:170px}}
th{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;white-space:nowrap}}
td.r,th.r{{text-align:right}}
td.up{{color:var(--up);font-weight:700}} td.down{{color:var(--down);font-weight:700}}
.bars{{display:grid;gap:8px}}
.brow{{display:grid;grid-template-columns:minmax(0,250px) 1fr 30px;gap:10px;align-items:center;font-size:14px}}
.brow .track{{height:12px;background:var(--bg);border-radius:4px;overflow:hidden}}
.brow .fill{{height:100%;background:var(--bar);border-radius:0 4px 4px 0}}
.brow .v{{text-align:right}}
details summary{{cursor:pointer;font-weight:700;color:var(--blue-ink)}}
.src{{font-size:12.5px;color:var(--muted);border-top:1px solid var(--rule);padding-top:10px}}
ul.checks{{list-style:none;margin:0;padding:0;display:grid;gap:4px;font-size:14px;color:var(--ink-2)}}
ul.checks span{{display:inline-block;width:20px;font-weight:900}} span.ok{{color:var(--down)}} span.no{{color:var(--warn-ink)}}
ul.checks b{{margin-right:6px}}
ul.next{{margin:0;padding-left:18px;color:var(--ink-2)}} ul.next li{{margin:4px 0}}
footer{{font-size:12.5px;color:var(--muted);text-align:center;padding-top:6px}}
</style>

<div class="wrap">
<header>
  <p class="kicker">Political Appointment · State of the Seat · {edition}</p>
  <h1>What changed this month</h1>
  <div class="seat">{esc(seat)}</div>
  <p class="small">Westminster constituency, July 2024 boundaries ({esc(p.get("seat_code", ""))}). Each source is shown with the latest month it covers.</p>
</header>
{banner}

<section>
  <h2>The headlines</h2>
  <ul class="lead">
    <li><span class="tag">Crime</span><span><b>{last["total"]:,} crimes recorded in {mlabel(last["month"])}</b>, {sp(crime_yoy_m)} on the same month last year. Over twelve months crime is {sp(crime_yoy_12)}, with violence and sexual offences {sp(vio)} and burglary {sp(bur)}.</span></li>
    <li><span class="tag">Jobs</span><span><b>{jl["count"]:,.0f} people claiming</b> unemployment-related benefits in {mlabel(jl["month"])} ({jl["rate"]}% of working-age residents), {sp(j_yoy, 1)} on a year ago. Across the UK the count rose {sp(uk_yoy, 1)} and the rate is {ukl["rate"] if ukl else "–"}%.</span></li>
    <li><span class="tag">Housing</span><span>{f'<b>£{hl["average_price"]:,.0f} average house price</b> in {esc(AREA.get(house.get("area", ""), house.get("area", "").replace("-", " ").title()))} in {mlabel(hl["month"])}, {sp(hl["annual_change_pct"], 1)} on a year ago.' if hl else "House prices unavailable this month."}</span></li>
    <li><span class="tag">Business</span><span><b>{el["insolvencies"]} insolvencies and {el["petitions"]} winding-up petitions</b> in {mlabel(latest_full)} at companies based in the seat. {(top_groups[0][1].split(" (")[0] + " is the most common sector among insolvencies over the past year.") if top_groups else ""}</span></li>
  </ul>
</section>

<section>
  <h2>Business distress</h2>
  <p>Insolvencies at companies registered in the constituency, and winding-up petitions (a creditor asking the court to close a company; a petition is not an insolvency, and many are paid off or dismissed).</p>
  <div class="legend"><span><i style="background:var(--bar)"></i>Insolvencies</span><span><i style="background:var(--bar-3)"></i>Winding-up petitions</span>{'<span><i style="background:var(--warn-bg);border:1px solid var(--warn-rule)"></i>Being re-checked</span>' if gap else ''}</div>
  {bars_svg(erows, gap)}
  <p class="small">Numbers for one seat are small, so a single month moves a lot. The value is in who and what: the list below.</p>
  <h3 style="font-size:16px;margin-top:6px">Which sectors, last 12 months</h3>
  <div class="bars">{"".join(f'<div class="brow"><span>{esc(g)}</span><div class="track"><div class="fill" style="width:{n / gmax * 100:.0f}%"></div></div><span class="v num">{n}</span></div>' for n, g in top_groups)}</div>
  <h3 style="font-size:16px;margin-top:6px">Insolvencies, newest first</h3>
  <div class="tbl"><table><tr><th>Date</th><th>Company</th><th>What happened</th><th>Sector</th><th>Since</th><th></th></tr>{named_table(ins_named, 14)}</table></div>
  {f'<details><summary>All {len(ins_named)} insolvencies in the last 13 months</summary><div class="tbl"><table><tr><th>Date</th><th>Company</th><th>What happened</th><th>Sector</th><th>Since</th><th></th></tr>{named_table(ins_named[14:], 200)}</table></div></details>' if len(ins_named) > 14 else ''}
  <h3 style="font-size:16px;margin-top:6px">Winding-up petitions (early warnings, not insolvencies)</h3>
  <div class="tbl"><table><tr><th>Date</th><th>Company</th><th>What happened</th><th>Sector</th><th>Since</th><th></th></tr>{named_table(pet_named, 10)}</table></div>
  <p class="src">Source: The Gazette, counted by Appointed; company details from Companies House. {esc(eco.get("note", ""))}</p>
</section>

<section>
  <h2>Jobs</h2>
  <div class="stats">
    <div class="stat"><div class="n num">{jl["count"]:,.0f}</div><div class="l">Claimants, {mlabel(jl["month"])}</div></div>
    <div class="stat"><div class="n num">{jl["rate"]}%</div><div class="l">Of residents aged 16–64 (UK {ukl["rate"] if ukl else "–"}%)</div></div>
    <div class="stat"><div class="n num">{sp(j_yoy, 1)}</div><div class="l">On a year ago (UK {sp(uk_yoy, 1)})</div></div>
  </div>
  <div class="legend"><span><i style="background:var(--bar)"></i>{esc(seat)}</span><span><i class="dash"></i>UK</span></div>
  {line_svg([(seat, "--bar", [(r["month"], r["rate"]) for r in jm], False), ("UK", "--ref", [(r["month"], r["rate"]) for r in jobs["uk"]], True)], fmt=lambda v: f"{v:.1f}%")}
  <p class="src">Source: Office for National Statistics, Claimant Count, via Nomis. {esc(jobs.get("note", ""))}</p>
</section>

<section>
  <h2>Crime</h2>
  <div class="stats">
    <div class="stat"><div class="n num">{last["total"]:,}</div><div class="l">Crimes recorded, {mlabel(last["month"])}</div></div>
    <div class="stat"><div class="n num">{sp(crime_yoy_m)}</div><div class="l">On {mlabel(prev["month"]) if prev else "a year ago"}</div></div>
    <div class="stat"><div class="n num">{sp(crime_yoy_12)}</div><div class="l">Last 12 months on the 12 before</div></div>
  </div>
  {line_svg([("Crimes", "--bar", [(r["month"], r["total"]) for r in cm], False)])}
  <div class="tbl"><table><tr><th>Type</th><th class="r">Last 12<br>months</th><th class="r">12 months<br>before</th><th class="r">Change</th></tr>{crime_rows}</table></div>
  <p class="src">Source: data.police.uk (Home Office), street-level crime inside the constituency boundary. {esc(crime.get("note", ""))}</p>
</section>

<section>
  <h2>Housing</h2>
  {f'''<div class="stats">
    <div class="stat"><div class="n num">£{hl["average_price"]:,.0f}</div><div class="l">Average price, {mlabel(hl["month"])}</div></div>
    <div class="stat"><div class="n num">{sp(hl["annual_change_pct"], 1)}</div><div class="l">On a year ago</div></div>
    <div class="stat"><div class="n num">{next((r["sales_volume"] for r in reversed(hm) if r["sales_volume"]), "–")}</div><div class="l">Sales registered, latest complete month</div></div>
  </div>
  {line_svg([("Average price", "--bar", [(r["month"], r["average_price"]) for r in hm], False)], fmt=lambda v: f"£{v / 1000:,.0f}k")}''' if hl else '<p>Unavailable this month.</p>'}
  <p class="src">Source: HM Land Registry, UK House Price Index. {esc(house.get("note", ""))}</p>
</section>

<section>
  <h2>Coming in later editions</h2>
  <ul class="next">
    <li><b>New companies.</b> Businesses set up in the seat each month, by sector, from Companies House. The other side of the distress figures.</li>
    <li><b>Schools.</b> Ofsted inspection results as they are published.</li>
    <li><b>Health.</b> GP access and hospital waiting times for the local trust.</li>
    <li><b>Planning.</b> Major applications and decisions.</li>
    <li><b>Alerts.</b> An email the day a notable local company enters insolvency, not just once a month.</li>
  </ul>
</section>

<section>
  <h2>How these figures are checked</h2>
  <p>Every source is checked automatically before anything is used. If a check fails, the figure is held back and marked, never estimated.</p>
  <ul class="checks">{"".join(checks)}</ul>
</section>

<footer>Political Appointment, from Appointed · Information from public records, presented without comment on any party or person · Built {built}</footer>
</div>
"""
    open(dst, "w").write(page)
    print("wrote", dst)


if __name__ == "__main__":
    main()
