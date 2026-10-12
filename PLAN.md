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
| A4 | No real location data in the proof: ETA is simulated. WhatsApp is a separate gated spike (see *WhatsApp plan*) | n/a |
| A5 | Exactly 10 products, per the brief; size and modifier options are a TRC addition approved by Richard, not a brief requirement | Load without attributes |

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
| Proof | One mock venue, 10 products | `data/products.csv` (10 rows, loader enforces) | C |
| Proof | Simulated kitchen queue and changing ETA | Kanban board + `x_eta_event` scenario rows + simulated clock | Sim |
| Proof | Delayed customer, overloaded kitchen | Scenarios S2 and S4 below | Sim |
| Proof | Report build time, gaps, risks, test outcomes | `EVIDENCE.md` + timed effort log | n/a |
| Proof | No production claim from UI mockup | Report states SaaS/simulated scope explicitly | n/a |
| Verify list | Kitchen display / POS API / queue telemetry | **Gap**: in Odoo 20 kitchen preparation orders (`pos.prep.order`) are created by the POS front end and cannot be held on SaaS; production needs a custom module (Odoo.sh / on-prem) | **Gap** |
| Verify list | Consent, minimisation, revocation, deletion of location data | No real location data. Consent flag + ETA only; `Withdraw consent` deletes ETA data (never tracked) and falls back to pickup time | S |
| Verify list | Cancellations, refunds, late customers | Cancel button → state `cancelled` and refund via native POS refund; late handled by S3 | N/S |
| Verify list | Fraud, traffic changes, poor connectivity | Not tested; listed as risks in report | **Gap** |
| Verify list | WhatsApp live location lawful/technical integration | Verified **not available**: see *WhatsApp plan* | **Gap** (by platform) |

## WhatsApp plan

**Finding (answers the brief's first verify item):** the WhatsApp Business Platform does not
deliver **live** location. A live-location share reaches the business webhook as an
`unsupported` message with no coordinates (Meta webhook reference; Twilio and ActiveCampaign
document the same limit). A **static** location pin, sent once, is supported. *Verify* on Meta's
current docs at spike time, because this can change.

**Decision: use WhatsApp as the customer channel, not the location feed.** The ETA comes from
customer taps instead of a location stream. This also gives better data minimisation for consent
(brief verify item 5).

| Use | Mechanism | Feeds |
|---|---|---|
| Order confirmed + "Share your ETA?" opt-in | Approved utility template with quick-reply buttons | `x_location_consent` |
| ETA signal | Quick replies: "10 min away" / "5 min away" / "I'm here" / "Running late" | `x_eta` = now + chosen minutes |
| One-off pin (optional) | Static location message → straight-line distance ÷ assumed speed | `x_eta` (coarse; no routing on SaaS) |
| Go to express lane / order ready | Utility templates sent from the release record | Journey step 6 |
| Revised collection time / late alert | Utility template | Flow G→I, acceptance check 2 |
| Stop sharing | Quick reply "Stop" → `Withdraw consent` | Revocation (S9) |

**Odoo fit (to verify in the spike):**
- Odoo's own WhatsApp app (Enterprise) sends templates from any model, including `x_pickup_release`. Outbound messages are expected to work on SaaS.
- The unknown is **inbound**: whether an automation on incoming WhatsApp messages can read a quick-reply payload and update `x_eta` on Odoo Online. If it can't, inbound handling needs middleware or an Odoo.sh module. That is the production path anyway.

**Prerequisites (lead time, not build time):**
- Meta Business Manager account, verified, with a dedicated test phone number.
- WhatsApp Business Account linked to the Odoo DB.
- Utility templates submitted and approved by Meta.
- Per-conversation fees (*verify* current Meta pricing).
- Record US opt-in consent wording before any real number is messaged. Synthetic/test numbers only in the lab.

**Sequencing:** the bounded proof runs on the simulated ETA, as the brief specifies. The WhatsApp
spike runs in parallel from Day 0 (Meta setup has lead time) and is time-boxed to 2 days once
templates are approved.
- **Pass:** a quick-reply tap changes the release time on the board with no manual step.
- **Fail:** documented as a SaaS gap with the middleware/module estimate.

## Build design (all in-DB, no custom Python module)

**Built:** step-by-step configuration in [`studio/BUILD_GUIDE.md`](studio/BUILD_GUIDE.md). The ten
server actions in [`studio/actions/`](studio/actions/) are paste-ready and tested offline under the
Odoo 20 sandbox rules ([`EVIDENCE.md`](EVIDENCE.md)).

- **Models:** `x_pickup_release` (one per paid order, chatter), `x_venue_config` (simulated clock,
  capacity, buffer, venue timezone), `x_eta_event` (scripted ETA changes).
- **Pickup time is always known:** the only self-order preset uses timed slots, so every order
  carries `preset_time`. Consent plus ETA, when given, takes precedence.
- **Release rule:** release = target − prep − queue wait − buffer. Queue wait = prep minutes of
  released/revised/preparing orders ÷ baristas. When due: release, or mark `revised` with a new
  collection time if the kitchen cannot meet the target. A released order the kitchen has not
  accepted is pulled back to `held` if the ETA moves later.
- **Late alert** is a flag (`x_late_alert`) plus a chatter alert, raised once when the customer will
  now arrive after the hold window of an order in preparation. The kitchen state is unchanged.
- **Override:** staff enter a release time and a mandatory reason. The ETA no longer moves it.
  User, reason and time are posted to chatter.
- **Privacy:** ETA-derived fields are not tracked and messages never contain arrival times, so a
  consent withdrawal leaves no arrival data behind.

## Acceptance tests (brief acceptance checks → scenarios)

Run each from a reset scenario with the clock at 08:00, 2 baristas, 1 min buffer.

| ID | Brief check | Scenario | Expected |
|---|---|---|---|
| S1 | Baseline | Latte (3 min), consent, ETA 08:15 | Held until 08:11, released, ready 08:14, collected |
| S2 | Delayed ETA postpones release | Panini (7 min), ETA 08:15 then 08:25 at 08:03 | Release moves 08:07 → 08:17; never released early |
| S3 | Late change after prep | Mocha Frost (5 min, hold 4), released, ETA +15 min after Accept | Late-alert flag + one chatter alert; order stays in preparation |
| S4 | Overloaded kitchen / early arrival cannot force impossible deadline | 6 food orders released at 08:00, new panini order with ETA 08:05 | `revised`, new collection time ≥ 08:05 + queue; customer message posted |
| S5 | Decline location | Cold Brew, no consent, pickup slot 08:30 | Released at 08:28 from pickup time; flow works without ETA |
| S6 | Traceability | Any released order | Links to one paid POS order with a unique ref; no release exists without payment |
| S7 | Staff override with audit | Override S2 release to 08:10, reason "regular, early" | Release at 08:10 despite later ETA change; chatter shows user, time, reason |
| S8 | Reconcile | Close POS session after S1–S7 | Journal entries posted; muffin stock reduced |
| S9 | Consent withdrawal | Withdraw consent on an S2-type order | ETA and scripted ETA events deleted, falls back to pickup time, no arrival time left in chatter |

## Deprioritised alternatives

- **Self-hosted or Odoo.sh with a `trc_order_release` Python module.** This would hold orders in
  the real Preparation Display and capture consent in the ordering UI. It is the production path,
  not this proof: it costs more and the target DB is SaaS.
- **WhatsApp live location as the ETA feed.** Not available on the WhatsApp Business Platform (below).
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
| W0 | Meta Business verification, test number, link WhatsApp app, submit templates | Alex | Day 0 (lead time) |
| W1 | WhatsApp spike: outbound templates + inbound quick-reply → `x_eta` (2-day box after approval) | Richie | After W0 |
| 7 | Review: approve / revise / production-path decision (Odoo.sh module) | Richard + Alex | Day 8 |

Log effort per step from Day 0. Build time is a brief deliverable, not optional.
