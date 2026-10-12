# Mundo Coffee: build plan for the order-release proof

**Target DB:** `pstest-trc-mundo-coffee.odoo.com` (Odoo Online / SaaS).
**Governing requirement:** *Project Moonshot: Mundo Coffee Demonstration Brief* (transcript 19:01–22:12).
**Status:** plan, not yet built. Synthetic data only; Mundo Coffee is fictional and implies no affiliation with any real chain.

## Objective

Prove on a clean Odoo database that a prepaid pickup order can be released to the kitchen at a
calculated safe time. The release time comes from a simulated changing ETA, or from a
customer-chosen pickup time when location is declined. The proof must handle one delayed
customer and one overloaded kitchen, and report build time, platform gaps, risks and test outcomes
(brief: *Bounded proof*).

## Decision

**Build the release engine inside Odoo Online using Studio fields, one Studio model with chatter,
and server actions, driven by a simulated clock.** Use the native POS and Self-Order for ordering,
payment and accounting. Do not touch the native Preparation Display. The brief asks for a
*simulated* kitchen queue, so it is a Studio kanban board.

Confidence: **Medium**. The design is sound for SaaS. Three unknowns about this DB (below) can
change the details, but not the approach.

## Assumptions

| # | Assumption | If wrong |
|---|---|---|
| A1 | DB is Odoo 20 (or saas-19.x) with POS, Self-Order, Inventory, Accounting and Studio enabled | Re-check presets and payment-provider steps |
| A2 | US company, USD, single state sales tax, Odoo demo data **off** | Reset DB before loading |
| A3 | Payment is the **Demo** payment provider (no real cards, no PCI scope) | Use a test-mode provider |
| A4 | No real location data, no WhatsApp: ETA is simulated (brief: *What must be verified*) | n/a: out of scope by brief |
| A5 | 10 products in proof (`in_proof = Y`); size and modifier options are a TRC addition approved by Richard, not a brief requirement | Load without attributes |

**Decision-critical. Check these on Day 0 in Settings › About and the subscription page:**

1. **Plan / trial status.** Studio, and external API access, are tied to the Custom plan on Odoo
   Online (*verify*). A 15-day trial that expires would lose the evidence. Confirm the DB is a
   non-expiring partner/test DB.
2. **External API (JSON-2).** If not available on this plan, `load_menu.py` cannot run. Fall
   back to the standard CSV import screens for products and attributes. The release engine does
   not depend on the API (it is all in-DB).
3. **Version.** Confirm whether POS **presets with pickup time slots** exist (expected on 18+,
   *verify*). They supply the no-consent pickup time natively. Without them, pickup time is a
   field on the release record.

## Requirement traceability (brief → build)

Class: **N** native Odoo · **C** configuration · **S** Studio/server action (no-code/low-code on
SaaS) · **Sim** simulated per brief · **Gap** cannot be met on Odoo Online and goes in the report.

| Brief ref | Requirement | Build | Class |
|---|---|---|---|
| Journey 1 | Select a nearby participating location | One mock venue = one POS config with Self-Order (mobile) | N/C |
| Journey 2 | Choose items and pay before arrival | Self-Order mobile, pay online via Demo provider | N/C |
| Journey 2 | Optionally consent to location sharing | `x_location_consent` on the release record, set by the scenario. **The standard Self-Order UI cannot capture consent without custom front-end code** | Sim + **Gap** |
| Journey 3 | Estimate arrival, prep time, queue length, throughput | Simulated ETA events; prep time = product prep + modifier deltas; queue = released, unfinished prep load ÷ venue capacity | S/Sim |
| Journey 4 | Release engine: minimise waiting, avoid food going cold | Server action `Recalculate release` (algorithm below) | S |
| Journey 5 | Kitchen receives, accepts, prepares | Kanban "Kitchen Release Board" with Accept / Ready buttons | S/Sim |
| Journey 6 | Tell customer to use express pickup, with instructions | Chatter message + email template on release; SMS out of scope (IAP credits) | C/S |
| Journey 7 | Collected, complete, reconciled to POS, inventory, accounting | Collected button; native POS session close posts accounting; storable bakery items move stock | N |
| Flow B→D | No consent → customer-selected pickup time | POS preset time slot (if A3/check 3 holds) else `x_pickup_requested` | N or S |
| Flow G→I | Kitchen cannot meet target → revised time / notify | State `revised` + message with new collection time | S |
| Proof | One mock venue, 10 products | `in_proof = Y` rows | C |
| Proof | Simulated kitchen queue and changing ETA | Kanban board + `x_eta_event` scenario rows + simulated clock | Sim |
| Proof | Delayed customer, overloaded kitchen | Scenarios S2 and S4 below | Sim |
| Proof | Report build time, gaps, risks, test outcomes | `EVIDENCE.md` + timed effort log | n/a |
| Proof | No production claim from UI mockup | Report states SaaS/simulated scope explicitly | n/a |
| Verify list | Kitchen display / POS API / queue telemetry | **Gap**: native Preparation Display receives orders at payment and cannot be held on SaaS (*verify*); production needs a custom module (Odoo.sh / on-prem) | **Gap** |
| Verify list | Consent, minimisation, revocation, deletion of location data | No real location data. Consent flag + ETA only; `Withdraw consent` button clears ETA history and falls back to pickup time | S |
| Verify list | Cancellations, refunds, late customers | Cancel button → state `cancelled` and refund via native POS refund; late handled by S3 | N/S |
| Verify list | Fraud, traffic changes, poor connectivity | Not tested; listed as risks in report | **Gap** |

## Build design (all in-DB, no custom Python module)

### Fields (developer mode › Technical › Fields, or Studio; manual fields must start `x_`)

| Model | Field | Type |
|---|---|---|
| product.template | `x_prep_minutes`, `x_max_hold_minutes` | Integer |
| product.template | `x_allergens` | Char |
| product.attribute.value | `x_prep_delta_seconds` | Integer |

### Studio model `x_pickup_release` (chatter on, all fields tracked)

`x_name` (order ref) · `x_pos_order_id` (m2o pos.order, required) · `x_amount_paid` (related) ·
`x_location_consent` (bool) · `x_pickup_requested` (datetime) · `x_eta` (datetime) ·
`x_prep_minutes_total` (int) · `x_max_hold_minutes` (int, min of lines) · `x_release_at` ·
`x_ready_by` · `x_target_at` (datetime) · `x_state` (selection: held / released / preparing /
ready / collected / revised / late_alert / cancelled) · `x_override` (bool) · `x_override_reason`
(char) · `x_override_by` (m2o res.users).

Supporting Studio models: `x_venue_config` (barista capacity, buffer minutes, simulated `x_now`)
and `x_eta_event` (release, at simulated minute, new ETA): the scenario script.

### Automations (Studio › Automations; Python code server actions)

1. **Create release on payment.** Trigger: `pos.order` state becomes paid. Creates one
   `x_pickup_release`, copies prep totals, sets state `held`. This is the only creation path,
   which is acceptance check 3.
2. **Recalculate release** (on ETA/pickup change, and on each clock tick):

   ```text
   target    = ETA if consent else pickup_requested
   wait      = sum(prep of released+preparing orders) / barista capacity
   release   = target - prep_total - wait - buffer
   if state == held:
       if release <= now:                      # early arrival / tight order
           release now
           ready_by = now + wait + prep_total
           if ready_by > target: state = revised, post new collection time   # AC1, flow G->I
           else: state = released
       else: keep held, store release_at                                    # AC2 postpone
   if state in (preparing, ready) and ETA moved later
          and target > ready_by + max_hold:  state = late_alert, post alert # AC2 late change
   if x_override: skip recalculation, keep staff release_at                  # AC5
   ```

3. **Advance clock +1 min / +5 min** buttons on `x_venue_config`. They apply due `x_eta_event` rows,
   then run Recalculate for open releases. This makes the demo repeatable and avoids depending on
   scheduled-action frequency on SaaS.
4. **Kitchen buttons** on the kanban: Accept (`preparing`), Ready (sends express-pickup message),
   Collected, Cancel.
5. **Staff override**: set `x_release_at` plus a reason (required). Tracked in chatter with user and
   timestamp.

## Acceptance tests (brief acceptance checks → scenarios)

Run each from a reset scenario with the clock at 08:00, 2 baristas, 1 min buffer.

| ID | Brief check | Scenario | Expected |
|---|---|---|---|
| S1 | Baseline | Latte (3 min), consent, ETA 08:15 | Held until 08:11, released, ready 08:14, collected |
| S2 | Delayed ETA postpones release | Panini (7 min), ETA 08:15 then 08:25 at 08:03 | Release moves 08:07 → 08:17; never released early |
| S3 | Late change after prep | Mocha Frost (5 min, hold 4), released, ETA +15 min after Accept | `late_alert` posted; staff sees it on board |
| S4 | Overloaded kitchen / early arrival cannot force impossible deadline | 6 food orders released at 08:00, new panini order with ETA 08:05 | `revised`, new collection time ≥ 08:05 + queue; customer message posted |
| S5 | Decline location | Cold Brew, no consent, pickup slot 08:30 | Released at 08:28 from pickup time; flow works without ETA |
| S6 | Traceability | Any released order | Links to one paid POS order with a unique ref; no release exists without payment |
| S7 | Staff override with audit | Override S2 release to 08:10, reason "regular, early" | Release at 08:10; chatter shows user, old/new value, reason |
| S8 | Reconcile | Close POS session after S1–S7 | Journal entries posted; muffin/croissant stock reduced |
| S9 | Consent withdrawal | Withdraw consent on an S2-type order | ETA cleared, falls back to pickup time, chatter logged |

## Deprioritised alternatives

- **Self-hosted or Odoo.sh with a `trc_order_release` Python module.** This would hold orders in
  the real Preparation Display and capture consent in the ordering UI. It is the production path,
  not this proof: it costs more and the target DB is SaaS.
- **WhatsApp live location.** Excluded by the brief until lawful and technical access is verified.
- **External ETA simulator via the API.** Possible if the plan allows JSON-2. The in-DB
  simulated clock is more repeatable for demos and has no plan dependency.

## Next steps

| # | Step | Owner | When |
|---|---|---|---|
| 0 | Confirm version, plan, Studio + API availability, non-expiring DB; confirm demo data off, US company, USD, tax | Alex | Day 0 |
| 1 | Configure POS venue, Self-Order mobile, Demo payment provider, presets/time slots | Richie | Day 1 |
| 2 | Create `x_` fields; load 10 products + modifiers + notes (`load_menu.py` or CSV import); add images | Ryan | Day 1–2 |
| 3 | Build `x_pickup_release`, `x_venue_config`, `x_eta_event`, kanban board | Richie | Day 2–3 |
| 4 | Build automations 1–5 | Richie | Day 3–5 |
| 5 | Script scenarios S1–S9 as `x_eta_event` data; run and capture evidence (screens + chatter) | Ryan | Day 6 |
| 6 | `EVIDENCE.md`: build hours per step, traceability classes, gaps, risks, pass/fail | Ryan + Richie | Day 7 |
| 7 | Review: approve / revise / production-path decision (Odoo.sh module) | Richard + Alex | Day 8 |

Log effort per step from Day 0. Build time is a brief deliverable, not optional.
