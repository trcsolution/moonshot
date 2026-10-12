# Evidence: Mundo Coffee proof against the demonstration brief

**Status (2026-10-13): built and verified offline; not yet built in the target DB.**
The build environment cannot reach `pstest-trc-mundo-coffee.odoo.com` (network policy) and holds
no credentials. Every row marked *DB* still needs to be done and evidenced in the database by
following `studio/BUILD_GUIDE.md`.

The brief says "do not claim a production implementation from a UI mockup alone". This proof is
not production: the kitchen queue and ETA are simulated, as the brief specifies.

## What "verified offline" means

- The ten server actions in `studio/actions/` are the exact code to paste into Odoo.
- `tests/` runs them unchanged under the Odoo 20.0 sandbox rules (opcode whitelist, forbidden names,
  builtins; copied from `odoo/tools/safe_eval/evaluation.py` at commit `2993e06c`) and a minimal
  fake ORM. 22 tests pass.
- Mutation testing: deliberately breaking the release formula, queue-load filter, overload check,
  late-alert guard, payment guard or quantity rule makes the suite fail. The one surviving mutant
  (`> now` vs `>= now + 1 min`) is equivalent at 1-minute ticks.
- Field and trigger names were checked against Odoo 20.0 source: `pos.order` (`state` paid/done,
  `preset_time`, `tracking_number`, `amount_paid`), `pos.order.line.attribute_value_ids`,
  `pos.preset.use_timing`, `pos.note`, `product.attribute.display_type = multi`,
  `product.attribute.value.default_extra_price`, automation triggers `on_state_set`,
  `on_create_or_write`, `on_webhook` (`payload` in the action context).
- **Not proven offline:** Odoo ORM behaviour, Studio UI, Self-Order payment flow, accounting and
  stock postings, timing on Odoo Online. Those are DB evidence.

## Brief compliance

| Brief item | Status | Evidence |
|---|---|---|
| Journey 1: select participating location | *DB* (config) | BUILD_GUIDE 1.3–1.5 |
| Journey 2: choose items and pay before arrival | *DB* (native Self-Order + Demo provider) | BUILD_GUIDE 1.5–1.6 |
| Journey 2: optional consent to location sharing | Logic verified; **capture in ordering UI is a SaaS gap** | S9, webhook tests; Gaps 1 |
| Journey 3: ETA, prep time, queue, throughput | Verified offline | S2, S4, S4b, modifier prep test |
| Journey 4: release engine, minimise wait, avoid cold food | Verified offline | S1, S2, S2b, S3 |
| Journey 5: kitchen receives, accepts, prepares | Verified offline (simulated board) | S1, kitchen-button test |
| Journey 6: express pickup instruction | Verified offline (chatter); customer channel = WhatsApp spike | S1 |
| Journey 7: collected and reconciled to POS, inventory, accounting | Collected verified; **reconciliation is *DB*** | S1; S8 pending |
| Flow D: no consent → customer-selected pickup time | Verified offline | S5 |
| Flow G→I: cannot meet target → revised time | Verified offline | S4 |
| One mock venue, 10 products | Data verified (loader enforces 10) | `load_menu.py --check` |
| Simulated kitchen queue and changing ETA | Verified offline | S2, S3 (`x_eta_event` + clock) |
| One delayed customer, one overloaded kitchen | Verified offline | S2, S4 |
| AC1 early arrival cannot force impossible deadline | Verified offline | S4 |
| AC2 delayed ETA postpones; late change after prep alerts | Verified offline | S2, S2b, S3 |
| AC3 every release traceable to valid payment and unique ID | Verified offline; access rights *DB* | S6, S6b |
| AC4 declining location still usable | Verified offline | S5 |
| AC5 staff override with audit trail | Verified offline | S7, S7b |
| Verify: consent, minimisation, revocation, deletion | Verified offline | S9, no-arrival-time-in-chatter test |
| Verify: WhatsApp live location | **Not available on the platform**; plan in PLAN.md | Meta webhook reference |
| Report build time, gaps, risks, test outcomes | Template below; *DB* | — |

## Scenario results

| ID | Offline (fake ORM) | In DB |
|---|---|---|
| S1 baseline | Pass | ☐ |
| S2 delayed ETA | Pass | ☐ |
| S2b released-not-started pulled back | Pass | ☐ |
| S3 late alert after prep | Pass | ☐ |
| S4 overloaded kitchen | Pass | ☐ |
| S4b queue load brings release forward | Pass | ☐ |
| S5 declined location | Pass | ☐ |
| S6 / S6b traceability | Pass | ☐ |
| S7 / S7b override audit | Pass | ☐ |
| S8 POS close → journal entries, muffin stock | n/a offline | ☐ |
| S9 consent withdrawal | Pass | ☐ |

## Gaps (for the report)

1. **Consent in the ordering screen.** Standard Self-Order cannot ask for location consent or ETA
   without front-end code; on SaaS it is entered on the release (simulating the app). Production:
   custom module on Odoo.sh.
2. **Native kitchen display.** Odoo 20 creates `pos.prep.order` records from the POS front end
   when the order is sent. On SaaS this cannot be held until the release time, so the proof uses
   the Studio board. Production: custom module.
3. **WhatsApp live location** is not delivered by the Business Platform. Use quick-reply ETA via
   the `10_webhook_eta` route (spike W1).
4. **Prep time is summed per order** (conservative; assumes one person makes the whole order).
   Station-parallel prep is a production refinement.
5. **Untested risks:** fraud, sudden traffic changes, poor connectivity.

## Build time log (fill in during the DB build)

| Step (BUILD_GUIDE) | Who | Minutes | Notes / deviations |
|---|---|---|---|
| 1 Base configuration | | | |
| 2 Fields + data load | | | |
| 3 Custom models | | | |
| 4 Access rights | | | |
| 5 Automations + actions | | | |
| 6 Views | | | |
| 7 Scenarios S1–S9 | | | |
