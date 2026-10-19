#!/usr/bin/env python3
"""
Email-ready chart images, made after build.py.

  docs/charts/regions-latest.png        UK tile map of the regional Distress Index
                                        (13-week totals, 100 = 2024-25 average)
  docs/charts/regions-YYYY-MM-DD.png    the same, kept for each week

Email programs can't run the website's live charts, so the weekly issue uses this
picture instead. Needs matplotlib (installed in the workflow).
"""
import csv, os, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")
OUTDIR = os.path.join(ROOT, "docs", "charts")

# tile positions (column, row) - a simplified UK layout
TILES = {
    "Scotland": (2, 0, "Scotland"),
    "Northern Ireland": (0, 1, "N. Ireland"),
    "North East": (3, 1, "North East"),
    "North West": (2, 2, "North West"),
    "Yorkshire and The Humber": (3, 2, "Yorkshire\n& Humber"),
    "Wales": (1, 3, "Wales"),
    "West Midlands": (2, 3, "West\nMidlands"),
    "East Midlands": (3, 3, "East\nMidlands"),
    "East of England": (4, 3, "East"),
    "South West": (1, 4, "South West"),
    "South East": (2, 4, "South East"),
    "London": (3, 4, "London"),
}

# diverging scale around 100: blue = below the 2024-25 norm, red = above; grey = about normal
BANDS = [  # (upper bound, fill, label ink)
    (80, "#1c5cab", "#ffffff"),
    (90, "#6da7ec", "#0a1014"),
    (97, "#cde2fb", "#0a1014"),
    (103, "#f0efec", "#0a1014"),
    (110, "#f6c9c4", "#0a1014"),
    (125, "#ec8c84", "#0a1014"),
    (10 ** 9, "#c0342f", "#ffffff"),
]
LEGEND = ["< 80", "80–90", "90–97", "97–103", "103–110", "110–125", "125 +"]
NODATA = "#ffffff"
INK, MUTED, RULE = "#0a1014", "#6b7480", "#dde1e6"


def band(v):
    for hi, fill, ink in BANDS:
        if v < hi: return fill, ink
    return BANDS[-1][1], BANDS[-1][2]


def latest_regional():
    p = os.path.join(DATA, "index_regional.csv")
    if not os.path.exists(p): return None, {}
    rows = list(csv.DictReader(open(p)))
    if not rows: return None, {}
    wk = max(r["week_start"] for r in rows)
    out = {}
    for r in rows:
        if r["week_start"] == wk and r["region"] in TILES:
            out[r["region"]] = (float(r["index_13wk"]) if r["index_13wk"] else None,
                                float(r["vs_year_earlier_pct"]) if r["vs_year_earlier_pct"] else None)
    return wk, out


def draw(wk, vals, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.patches import FancyBboxPatch
    fam = "Inter" if any("Inter" in f.name for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
    plt.rcParams["font.family"] = fam

    W, H = 6.0, 7.2                     # inches; saved at 200 dpi -> 1200 x 1440 px
    fig = plt.figure(figsize=(W, H), dpi=200)
    fig.patch.set_facecolor("#ffffff")
    ax = fig.add_axes([0.04, 0.17, 0.92, 0.70]); ax.set_xlim(-0.1, 5.1); ax.set_ylim(5.1, -0.1); ax.axis("off")
    s, gap = 1.0, 0.07
    for reg, (c, r, label) in TILES.items():
        v, yoy = vals.get(reg, (None, None))
        fill, ink = band(v) if v is not None else (NODATA, MUTED)
        ax.add_patch(FancyBboxPatch((c + gap, r + gap), s - 2 * gap, s - 2 * gap,
                                    boxstyle="round,pad=0,rounding_size=0.08",
                                    facecolor=fill, edgecolor=RULE if v is None else fill, linewidth=1.2))
        ax.text(c + 0.5, r + 0.36, label, ha="center", va="center", fontsize=8.2, color=ink,
                linespacing=1.0, fontweight="semibold")
        ax.text(c + 0.5, r + 0.70, f"{v:.0f}" if v is not None else "–", ha="center", va="center",
                fontsize=15, color=ink, fontweight="heavy")
    end = (dt.date.fromisoformat(wk) + dt.timedelta(days=6)) if wk else None
    fig.text(0.05, 0.955, "Distress Index by region", fontsize=17, fontweight="heavy", color=INK, va="top")
    fig.text(0.05, 0.905, f"13 weeks to {end:%-d %B %Y}  ·  100 = 2024–25 average" if end else "",
             fontsize=10, color=MUTED, va="top")
    # legend
    lx, ly, lw = 0.05, 0.095, 0.9 / len(BANDS)
    for i, ((_, fill, _ink), lab) in enumerate(zip(BANDS, LEGEND)):
        fig.patches.append(FancyBboxPatch((lx + i * lw + 0.004, ly), lw - 0.008, 0.028,
                                          boxstyle="round,pad=0,rounding_size=0.004", transform=fig.transFigure,
                                          facecolor=fill, edgecolor=RULE, linewidth=0.6))
        fig.text(lx + i * lw + lw / 2, ly - 0.012, lab, ha="center", va="top", fontsize=7.5, color=MUTED)
    fig.text(0.05, 0.155, "Fewer insolvencies than normal", fontsize=8, color=MUTED, va="center")
    fig.text(0.95, 0.155, "More than normal", fontsize=8, color=MUTED, va="center", ha="right")
    fig.text(0.05, 0.03, "Appointed · built from every insolvency notice in The Gazette · "
             "a dash means too few cases to show", fontsize=7, color=MUTED)
    fig.savefig(path, dpi=200, facecolor="#ffffff")
    plt.close(fig)


def main():
    wk, vals = latest_regional()
    if not wk or not any(v for v, _ in vals.values()):
        print("charts: no regional index yet; skipped"); return
    os.makedirs(OUTDIR, exist_ok=True)
    end = (dt.date.fromisoformat(wk) + dt.timedelta(days=6)).isoformat()
    for name in ("regions-latest.png", f"regions-{end}.png"):
        draw(wk, vals, os.path.join(OUTDIR, name))
    print(f"charts: regional map for week starting {wk}")


if __name__ == "__main__":
    if len(sys.argv) > 1: DATA = sys.argv[1]; OUTDIR = sys.argv[2]
    main()
