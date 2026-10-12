# Build guide: Mundo Coffee release engine in Odoo Online

Click-path for `pstest-trc-mundo-coffee.odoo.com`. Do the steps in order and log minutes per step
in `EVIDENCE.md` (build time is a brief deliverable). Field names, triggers and sandbox rules
are verified against the Odoo **20.0** source (commit `2993e06c`). Menu paths are from
memory of recent versions (*verify* labels on the DB).

Work in **developer mode** (Settings › Activate developer mode).

## 1. Base configuration (native, no code)

| # | Where | Setting |
|---|---|---|
| 1.1 | Settings › Companies | US company, USD, venue address; Odoo demo data must be absent |
| 1.2 | Accounting › Configuration | US fiscal localisation; one state sales tax on prepared food and drinks (*verify* rate) |
| 1.3 | Point of Sale › Configuration › Point of Sales | New POS **Mundo Express**, restaurant mode on |
| 1.4 | POS › Configuration › Presets | Preset **Express Pickup**: *Manage orders by time* (`use_timing`) on, interval 5 min, capacity per slot 4, opening-hours calendar. Make it the only self-order preset, so every order carries a pickup time (`pos.order.preset_time`) |
| 1.5 | POS settings › Self Ordering | Mobile ordering, pay **online** before preparation |
| 1.6 | Accounting / Website › Payment Providers | **Demo** provider, enabled for the POS (no real cards) |
| 1.7 | Inventory | Muffin storable (stock reduces on sale); drinks and made-to-order food consumable |

## 2. Product data fields (Settings › Technical › Fields › New)

| Model | Field name | Type | Label |
|---|---|---|---|
| product.template | `x_prep_minutes` | Integer | Prep minutes |
| product.template | `x_max_hold_minutes` | Integer | Max hold minutes |
| product.template | `x_allergens` | Char | Allergens |
| product.attribute.value | `x_prep_delta_seconds` | Integer | Prep delta (s) |

Then load `data/` with `tools/load_menu.py` (needs external API on the plan), or with the
standard import screens. Load order: attributes, products, attribute lines, then POS notes.

## 3. Custom models (Settings › Technical › Models › New)

### `x_venue_config` "Venue Settings" (one record)

| Field | Type | Default / note |
|---|---|---|
| `x_name` | Char | Mundo Express |
| `x_now` | Datetime | Simulated clock; leave empty for real time |
| `x_tick_minutes` | Integer | 1 |
| `x_capacity` | Integer | 2 (baristas working in parallel) |
| `x_buffer_minutes` | Integer | 1 |
| `x_tz` | Char | `America/New_York` (venue timezone used in messages) |

### `x_pickup_release` "Pickup Release" (tick **Mail thread** for chatter)

| Field | Type | Tracking | Note |
|---|---|---|---|
| `x_name` | Char | | Order reference |
| `x_pos_order_id` | Many2one `pos.order` | | Required, on delete **restrict** |
| `x_state` | Selection | **Yes** | `held`, `released`, `revised`, `preparing`, `ready`, `collected`, `cancelled` |
| `x_location_consent` | Boolean | **Yes** | |
| `x_eta` | Datetime | **No** | Personal data; never tracked |
| `x_pickup_requested` | Datetime | No | From preset time |
| `x_target_at` | Datetime | **No** | Derived from ETA |
| `x_prep_minutes` | Integer | No | |
| `x_max_hold_minutes` | Integer | No | |
| `x_release_at` | Datetime | No | Override audit is posted as a message |
| `x_ready_by` | Datetime | No | |
| `x_late_alert` | Boolean | **Yes** | |
| `x_override` | Boolean | **Yes** | |
| `x_override_reason` | Char | **Yes** | |
| `x_override_by` | Many2one `res.users` | **Yes** | |
| `x_clock_at` | Datetime | No | Technical: touched by clock to trigger recalculation |
| `x_amount_paid` | Monetary, related `x_pos_order_id.amount_paid` | No | Display |
| `x_tracking_number` | Char, related `x_pos_order_id.tracking_number` | No | Display |

**Why ETA-derived fields are untracked:** tracking keeps old values in the chatter. A consent
withdrawal must remove arrival data, and chatter history cannot be cleared by the action.

### `x_eta_event` "Simulated ETA Event"

`x_name` (Char) · `x_release_id` (Many2one `x_pickup_release`, on delete cascade) ·
`x_at` (Datetime) · `x_new_eta` (Datetime) · `x_applied` (Boolean).

## 4. Access rights (Settings › Technical › Access Rights)

| Model | POS User | POS Manager |
|---|---|---|
| `x_pickup_release` | read, write | read, write, **no create**, no delete |
| `x_venue_config` | read | read, write |
| `x_eta_event` | none | read, write, create, delete |

No create rights on releases for anyone keeps automation 01 as the only creation path
(acceptance check 3). Automation code runs in the triggering user's environment (Odoo 20
`ir.actions.server.run`), so 01 creates with `sudo()`; every other action only writes.

## 5. Automations and actions

Paste each file from `studio/actions/` unchanged into an **Execute Code** action.
`python3 -m unittest discover -s tests` must pass before pasting.

| File | Type | Model | Trigger / button |
|---|---|---|---|
| `01_create_release_on_payment.py` | Automation | `pos.order` | **State is set to** Paid |
| `02_recalculate_release.py` | Automation | `x_pickup_release` | **On create and edit**, trigger fields `x_eta`, `x_pickup_requested`, `x_location_consent`, `x_override`, `x_clock_at` |
| `03_advance_clock.py` | Server action + button | `x_venue_config` | "Advance clock" |
| `04_kitchen_accept.py` | Server action + button | `x_pickup_release` | "Accept" |
| `05_kitchen_ready.py` | Server action + button | `x_pickup_release` | "Ready" |
| `06_collected.py` | Server action + button | `x_pickup_release` | "Collected" |
| `07_cancel.py` | Server action + button | `x_pickup_release` | "Cancel" |
| `08_apply_override.py` | Server action + button | `x_pickup_release` | "Apply override" |
| `09_withdraw_consent.py` | Server action + button | `x_pickup_release` | "Withdraw location consent" |
| `10_webhook_eta.py` | Automation (optional, WhatsApp spike) | `x_pickup_release` | **On webhook**; record getter `model.search([('x_name', '=', payload.get('order_ref'))], limit=1)` |

Sandbox rule (Odoo 20): no attribute assignment (`rec.x = ...` is rejected). The files only use
`write()`, which the test suite enforces.

## 6. Views (Studio)

- **Kitchen Release Board:** kanban on `x_pickup_release` grouped by `x_state`. Cards show order
  number, `x_release_at`, `x_ready_by`, prep minutes, and a red ribbon when `x_late_alert`. Buttons
  Accept / Ready / Collected. Default filter: state not collected/cancelled.
- **Release form:** all fields, buttons 04–09, chatter.
- **Venue Settings form:** clock, capacity, buffer, timezone, "Advance clock" button; embedded
  list of `x_eta_event`.

## 7. Run the acceptance scenarios

Set `x_now` to 08:00 local, capacity 2, buffer 1. Place each order through Self-Order (mobile)
and pay with the Demo provider. On the release, tick consent and enter the ETA (simulating the
app). Add `x_eta_event` rows for delayed customers, then press **Advance clock**. Expected
results are in `PLAN.md` (S1–S9) and are the assertions in `tests/test_release_engine.py`.
Capture screenshots of the board and chatter for each scenario in `EVIDENCE.md`.
