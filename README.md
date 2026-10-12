# Project Moonshot

TRC proof builds for Project Moonshot. Each proof starts from a clean Odoo environment,
uses synthetic data only, and records what is standard, configuration, development or a gap,
plus build time.

| Folder | Proof | Status |
|---|---|---|
| [`mundo-coffee/`](mundo-coffee/) | Prepaid pickup order-release engine (Odoo 20 Online, US) | Built and tested offline; DB build pending |
| — | Glenmare Dairy Foods (process manufacturing) | Not started |
| — | Kestrel Power Supplies (discrete manufacturing) | Not started |

Governing requirements: [`docs/briefs/`](docs/briefs/).

Mundo Coffee, Glenmare and Kestrel are fictional scenarios. They imply no affiliation with any
real company.

## Mundo Coffee quick start

```bash
cd mundo-coffee
python3 -m unittest discover -s tests      # 22 tests: server actions under Odoo 20 sandbox rules
python3 tools/load_menu.py --check         # validate the 10-product menu
```

Then follow [`mundo-coffee/studio/BUILD_GUIDE.md`](mundo-coffee/studio/BUILD_GUIDE.md) against the
target DB, with `ODOO_URL`, `ODOO_DB` and `ODOO_API_KEY` set in the local environment.
