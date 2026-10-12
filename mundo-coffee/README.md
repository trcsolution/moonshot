# Mundo Coffee: synthetic menu for the Odoo 20 order-release proof

TRC Odoo 20 Accelerator lab data. **Synthetic only.** Mundo Coffee is a fictional chain:
item names are generic coffee-shop terms, and no third-party trademarks, cup-size names,
logos or branded imagery may be added (see the brief's brand caveat).

Target DB: `pstest-trc-mundo-coffee.odoo.com` (Odoo Online), US localisation (USD), **Odoo demo data off**.
Build plan and brief traceability: [`PLAN.md`](PLAN.md). Exactly 10 products, as the brief specifies (the loader enforces it).
Size and modifier options are a TRC addition, not a brief requirement.

## Contents

| Path | What it is |
|---|---|
| `data/products.csv` | 10 menu items: base price (Small), POS category, prep and max-hold minutes, allergens, image file |
| `data/attributes.csv` | 7 modifier groups / 30 values, with price extras and prep-time deltas |
| `data/attribute_profiles.csv` | Which modifier groups each product type gets |
| `data/pos_notes.csv` | 18 free kitchen instructions (no charge), loaded as predefined POS notes |
| `images/MANIFEST.csv` | Image file names, search terms and licence record (images not yet sourced) |
| `tools/load_menu.py` | Validator and JSON-2 loader (`--check`, `--dry-run`, live) |
| `PLAN.md` | Build plan, brief traceability, acceptance scenarios, WhatsApp plan |
| `studio/BUILD_GUIDE.md` | Click-path to build the release engine in the Odoo Online DB |
| `studio/actions/` | Ten paste-ready server actions (release engine, clock, kitchen buttons, override, consent, webhook) |
| `tests/` | Runs the actions under Odoo 20 sandbox rules against scenarios S1–S9 (`python3 -m unittest discover -s tests`) |
| `EVIDENCE.md` | Brief compliance review, scenario results, gaps, build-time log |

## Modifier design

| Need | Odoo mechanism | Charged? |
|---|---|---|
| Size (12/16/20oz) | Attribute `Size`, creates variants | Yes: +$0.60 / +$1.10 |
| Milk swap (skim "skinny", oat, almond, soy...) | Attribute `Milk`, no variant, single choice | Plant milks +$0.60–0.70 |
| Decaf / half-caf | Attribute `Espresso`, no variant | No |
| Extra shot, syrups, drizzle, whip, cold foam | Attribute `Extras`, no variant, multi-checkbox | Yes: +$0.50–1.00 each |
| Extra hot, kids temp / light ice | Attributes `Temperature` / `Ice`, no variant | No |
| No cream, no whip, skinny, dry, upside down, allergy check... | Predefined POS notes | No |

Rule of thumb: **if it changes price, stock or prep time it is an attribute; if it is only an
instruction to the barista it is a note.** "Skinny" is in both places on purpose: the milk
choice drives the recipe, and the note tells the barista to also go sugar-free and skip the whip.

## Example orders (expected POS totals before sales tax)

| Order as spoken | Lines selected | Total | Est. prep |
|---|---|---|---|
| Large oat latte, extra shot, no foam | Caffè Latte · Large · Oat · Extras: shot · Note: No foam | 4.95 + 1.10 + 0.70 + 0.90 = **$7.65** | 3:35 |
| Medium skinny vanilla latte | Caffè Latte · Medium · Skim · Extras: SF vanilla · Note: Skinny | 4.95 + 0.60 + 0.60 = **$6.15** | 3:05 |
| Medium mocha frost, no whip | Mocha Frost · Medium · Note: No whipped cream | 6.25 + 0.60 = **$6.85** | 5:00 |
| Large iced latte, cold foam, light ice | Iced Latte · Large · Ice: Light · Extras: cold foam | 5.25 + 1.10 + 1.00 = **$7.35** | 3:35 |
| Small cappuccino, dry, decaf | Cappuccino · Small · Espresso: Decaf · Note: Dry | **$4.95** | 3:00 |
| Breakfast sandwich, no bacon, add avocado | Bacon & Egg Sandwich · Food extras: avocado · Note: No bacon | 5.95 + 1.25 = **$7.20** | 6:30 |
| Medium caramel macchiato, upside down, light drizzle | Caramel Macchiato · Medium · Notes: Upside down, Light caramel drizzle | 5.75 + 0.60 = **$6.35** | 4:00 |
| Blueberry muffin | Muffin | **$3.25** | 0:00 |

Use these as POS test cases: the totals check the price extras, and the prep column
checks the release engine's prep-delta logic (est. prep = product prep
minutes + sum of the selected values' `prep_delta_seconds`; Large adds 15s).

## Loading

```bash
python3 tools/load_menu.py --check      # validate CSVs + manifest, no Odoo needed
python3 tools/load_menu.py --dry-run    # show what would load
ODOO_URL=https://... ODOO_DB=mundo_us ODOO_API_KEY=... python3 tools/load_menu.py
```

- Re-runnable: records are matched on name / `default_code` and updated in place.
- Uses the JSON-2 API (`/json/2/<model>/<method>`), not XML-RPC.
- Custom fields (`x_prep_minutes`, `x_max_hold_minutes`, `x_allergens`,
  `x_prep_delta_seconds`) are written only if they exist. Create them first (PLAN.md).
- External API access on Odoo Online depends on the plan (*verify*). If it is unavailable,
  use the standard CSV import screens with the same files.
- Sales tax is not set by the loader. Configure it from the US fiscal localisation for the
  chosen state.

Confirmed in Odoo 20.0 source: `default_extra_price` on attribute values, the `multi`
display type, and the `pos.note` model. **Still to verify on the DB:** the JSON-2 request body
format and external API access on the plan. The loader skips or warns where a field or model
is missing rather than failing.

## Images

No images are committed yet: the build environment's network policy blocked the stock
photo hosts. To add them, for each row in `images/MANIFEST.csv`:

1. Search Unsplash or Pexels with the `search_terms`. Both licences allow free commercial
   use (*verify* current terms), but neither allows implying endorsement.
2. Reject any image with a visible logo, branded cup or sleeve, a recognisable store
   interior or an identifiable person.
3. Save it as `image_file` (JPG, square crop, at least 1024px) and fill in `source_url`,
   `photographer`, `licence` and `brand_check_passed`.

`--check` fails if an image is present without a licence and source URL.

## Allergens

The allergen column uses the US major allergens. It is illustrative recipe data, not a
labelling claim. Plant-milk and syrup swaps add allergens (almond and hazelnut are tree
nuts; soy). The "ALLERGY - please check with guest" note is the stop-and-verify control.
