# appointed-data

Public, aggregated data behind **Appointed**'s UK insolvency heat map and the **Appointed distress index**.

Every night a small program (`pipeline/build.py`, run by GitHub Actions) reads UK corporate insolvency notices from **The Gazette** (London, Edinburgh and Belfast editions), turns notices into **events** (one per company per procedure), and publishes **counts only**.

## What the index counts

The headline counts only the three procedures the law requires to be published in The Gazette, which together make up about 99% of UK company insolvencies:

| Component | Gazette codes |
|---|---|
| Administrations | 2410 |
| Creditors' voluntary liquidations | 2441 and 2443, merged into one event per company |
| Winding-up orders | 2452 |

**Winding-up petitions** (2450, 2451) are a separate early-warning indicator from April 2022, with HMRC petitions shown separately. A petition is a creditor's request, not a failure.

Receiver appointments (2423), administrative receiverships (2421) and disclaimers (2603) are kept as memo items only: there is no legal duty to gazette most of them, so coverage is unknown. Members' voluntary liquidations (solvent closures) are excluded.

## Rules

- **One event per company per procedure.** Repeat notices for the same company within 365 days (120 for CVLs, 180 for petitions) are not counted again. Companies with an administration in the previous 18 months are not counted as new CVLs.
- **Dated by publication week.** The free feed does not show the appointment or order date, so each event is dated by the week its first notice appeared.
- **100 = the 2024-25 average** ("recent normal", not a long-run average).
- **Weights** are set so each component's typical week-to-week wobble counts equally (Conference Board method), and published in `meta.json`.
- **Small numbers:** regional figures use 13-week totals, and anything under 20 events is not shown.
- **The latest four weeks are provisional.**
- Between spring 2020 and 31 March 2022 the law restricted winding-up petitions, so petition and winding-up order numbers in that period are artificially low.

## Files (`docs/data/`)

| File | What it is |
|---|---|
| `index_weekly.csv` | Headline index, equal-weight and plain-count versions, each component, petitions indicator |
| `index_regional.csv` | 13-week totals and index by region |
| `diffusion_regions.csv` | Share of regions where insolvencies are up on a year earlier (50 = neutral) |
| `weekly_components.csv` | Weekly event counts by component, nation and region |
| `monthly_england_wales.csv` | Monthly counts for England and Wales, for checking against the Insolvency Service |
| `summary.json` | Latest week at a glance |
| `meta.json` | Method, weights, baseline, data-quality measures, sources |
| `last_run.md` | Log of the latest run |

## Not published

No company names or numbers, notice text, addresses or map points.

## Status

This is not an official statistic. The Insolvency Service's monthly figures are the authoritative measure.

Contains public sector information licensed under the Open Government Licence v3.0. Source: The Gazette. Region lookups: postcodes.io (ONS Postcode Directory, Open Government Licence).
