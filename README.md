# appointed-data

Public, aggregated data behind the **Appointed** UK insolvency heat map.

Every day a small program (`pipeline/build.py`, run by GitHub Actions) reads UK corporate insolvency notices from **The Gazette**, works out which region each one belongs to, and publishes **weekly counts only**.

## Files (`docs/data/`)

| File | What it is |
|---|---|
| `weekly_region.csv` | Notices per week, by notice type and region |
| `weekly_uk.csv` | UK totals per week, by notice type, with how many could be placed in a region |
| `summary.json` | Latest complete week against each region's own 52-week average |
| `meta.json` | When it last ran, coverage, definitions and sources |
| `monthly/` | The same counts stored month by month (lets the history build up in stages) |
| `last_run.md` | The log from the most recent run |

## What's counted

Administrations, administrative receiverships, receiverships, creditors' voluntary liquidations, winding-up orders, winding-up petitions and disclaimers. Members' voluntary liquidations (solvent closures) are **not** counted.

Weeks are the week a notice was **published**, which is usually a few days after the event itself.

Between 27 April 2020 and 31 March 2022 the law restricted winding-up petitions, so petition and winding-up order numbers in that period are artificially low.

## What's not published

No company names, notice text, addresses or map points. They are used only while the program runs, to find the region.

## Sources

- The Gazette, under the Open Government Licence
- postcodes.io (ONS Postcode Directory), under the Open Government Licence
