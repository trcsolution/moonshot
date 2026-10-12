"""Brief acceptance scenarios S1-S9 (PLAN.md) run against the real server-action files.

Run from odoo-accelerator/mundo-coffee:  python3 -m unittest discover -s tests -v
"""
import csv
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from odoo_sandbox import Env, UserError, check_code, compile_action, run

ROOT = Path(__file__).resolve().parent.parent
ACTIONS = ROOT / 'studio' / 'actions'
CODE = {p.stem: compile_action(p) for p in sorted(ACTIONS.glob('*.py'))}

SCHEMA = {
    'pos.order': {'lines': ('x2m', 'pos.order.line')},
    'pos.order.line': {'product_id': ('m2o', 'product.product'),
                       'attribute_value_ids': ('x2m', 'product.template.attribute.value')},
    'product.product': {'product_tmpl_id': ('m2o', 'product.template')},
    'product.template': {},
    'product.template.attribute.value': {'product_attribute_value_id': ('m2o', 'product.attribute.value')},
    'product.attribute.value': {},
    'x_venue_config': {},
    'x_pickup_release': {'x_pos_order_id': ('m2o', 'pos.order'), 'x_override_by': ('m2o', 'res.users')},
    'x_eta_event': {'x_release_id': ('m2o', 'x_pickup_release')},
    'res.users': {},
}
RECALC_TRIGGERS = {'x_eta', 'x_pickup_requested', 'x_location_consent', 'x_override', 'x_clock_at'}


def read_csv(name):
    with open(ROOT / 'data' / name, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def t(hhmm):
    h, m = hhmm.split(':')
    return datetime(2026, 10, 13, int(h), int(m))


class Lab:
    """One clean simulated venue: 08:00, 2 baristas, 1 min buffer, menu from data/*.csv."""

    def __init__(self):
        env = self.env = Env(SCHEMA)
        env.automations = [
            ('pos.order', {'state'}, CODE['01_create_release_on_payment'], '01'),
            ('x_pickup_release', RECALC_TRIGGERS, CODE['02_recalculate_release'], '02'),
        ]
        self.cfg = env['x_venue_config'].create(
            {'x_name': 'Mundo Express', 'x_now': t('08:00'), 'x_capacity': 2, 'x_buffer_minutes': 1,
             'x_tick_minutes': 1})
        self.products, self.values = {}, {}
        for r in read_csv('products.csv'):
            tmpl = env['product.template'].create({'name': r['name'], 'x_prep_minutes': int(r['prep_minutes']),
                                                   'x_max_hold_minutes': int(r['max_hold_minutes'])})
            self.products[r['name']] = env['product.product'].create({'product_tmpl_id': tmpl.id})
        for r in read_csv('attributes.csv'):
            pav = env['product.attribute.value'].create(
                {'name': r['value'], 'x_prep_delta_seconds': int(r['prep_delta_seconds'])})
            self.values[r['value']] = env['product.template.attribute.value'].create(
                {'product_attribute_value_id': pav.id})
        self.n = 0

    def order(self, items, pickup, paid=True):
        """items: [(product name, qty, [attribute values])]. Returns the release (or the order if unpaid)."""
        self.n += 1
        lines = [self.env['pos.order.line'].create({
            'product_id': self.products[name].id, 'qty': qty,
            'attribute_value_ids': [self.values[v].id for v in vals]}).id for name, qty, vals in items]
        order = self.env['pos.order'].create({'name': f'Shop/{self.n:04d}', 'pos_reference': f'Order 00001-001-{self.n:04d}',
                                              'tracking_number': str(100 + self.n), 'lines': lines,
                                              'state': 'draft', 'amount_paid': 0, 'preset_time': t(pickup)})
        if not paid:
            return order
        order.write({'state': 'paid', 'amount_paid': 9.99})
        return self.env['x_pickup_release'].search([('x_pos_order_id', '=', order.id)])

    def share_eta(self, rel, eta):
        rel.write({'x_location_consent': True, 'x_eta': t(eta)})

    def eta_event(self, rel, at, eta):
        self.env['x_eta_event'].create({'x_release_id': rel.id, 'x_at': t(at), 'x_new_eta': t(eta), 'x_applied': False})

    def tick_to(self, hhmm):
        while self.cfg.x_now < t(hhmm):
            run(CODE['03_advance_clock'], '03', self.env, self.cfg)

    def act(self, name, rel):
        run(CODE[name], name, self.env, rel)

    def msgs(self, rel):
        return self.env.messages.get(('x_pickup_release', rel.id), [])


class SandboxTests(unittest.TestCase):
    def test_all_actions_pass_odoo20_sandbox(self):
        self.assertEqual(len(CODE), 10)  # compile_action already raised if any were unsafe

    def test_checker_rejects_attribute_assignment(self):
        with self.assertRaises(ValueError):
            check_code(compile("rec.x_state = 'held'", 'bad', 'exec'), 'bad')

    def test_checker_rejects_imports_and_dunders(self):
        for src in ('import os', 'x = ().__class__'):
            with self.assertRaises((ValueError, NameError)):
                check_code(compile(src, 'bad', 'exec'), 'bad')


class AcceptanceScenarios(unittest.TestCase):
    def setUp(self):
        self.lab = Lab()

    def test_s1_baseline_release_and_collection(self):
        lab = self.lab
        rel = lab.order([('Caffè Latte', 1, [])], pickup='08:20')
        lab.share_eta(rel, '08:15')
        self.assertEqual((rel.x_state, rel.x_release_at), ('held', t('08:11')))
        lab.tick_to('08:10')
        self.assertEqual(rel.x_state, 'held')
        lab.tick_to('08:11')
        self.assertEqual((rel.x_state, rel.x_ready_by), ('released', t('08:14')))
        for step, state in (('04_kitchen_accept', 'preparing'), ('05_kitchen_ready', 'ready'), ('06_collected', 'collected')):
            lab.act(step, rel)
            self.assertEqual(rel.x_state, state)
        self.assertIn('express pickup lane', lab.msgs(rel)[-1])

    def test_s2_delayed_eta_postpones_release(self):
        lab = self.lab
        rel = lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:40')
        lab.share_eta(rel, '08:15')
        self.assertEqual(rel.x_release_at, t('08:07'))
        lab.eta_event(rel, '08:03', '08:25')
        lab.tick_to('08:03')
        self.assertEqual((rel.x_state, rel.x_release_at), ('held', t('08:17')))
        lab.tick_to('08:16')
        self.assertEqual(rel.x_state, 'held')
        lab.tick_to('08:17')
        self.assertEqual(rel.x_state, 'released')

    def test_s2b_released_but_not_started_is_pulled_back(self):
        lab = self.lab
        rel = lab.order([('Americano', 1, [])], pickup='08:40')
        lab.share_eta(rel, '08:05')
        lab.tick_to('08:02')
        self.assertEqual(rel.x_state, 'released')
        lab.eta_event(rel, '08:03', '08:20')
        lab.tick_to('08:03')
        self.assertEqual((rel.x_state, rel.x_release_at), ('held', t('08:17')))
        self.assertIn('postponed', lab.msgs(rel)[-1])

    def test_s3_late_change_after_prep_raises_alert(self):
        lab = self.lab
        rel = lab.order([('Mocha Frost', 1, [])], pickup='08:30')
        lab.share_eta(rel, '08:10')
        lab.tick_to('08:04')
        self.assertEqual((rel.x_state, rel.x_ready_by), ('released', t('08:09')))
        lab.act('04_kitchen_accept', rel)
        lab.eta_event(rel, '08:05', '08:25')
        lab.tick_to('08:05')
        self.assertTrue(rel.x_late_alert)
        self.assertEqual(rel.x_state, 'preparing')
        self.assertIn('LATE ALERT', lab.msgs(rel)[-1])
        lab.tick_to('08:06')
        self.assertEqual(sum('LATE ALERT' in m for m in lab.msgs(rel)), 1)  # alerts once

    def test_s4_overloaded_kitchen_early_arrival_gets_revised_time(self):
        lab = self.lab
        for name in ['Cheese & Tomato Panini'] * 3 + ['Bacon & Egg Breakfast Sandwich'] * 3:
            busy = lab.order([(name, 1, [])], pickup='08:45')
            busy.write({'x_state': 'preparing'})  # kitchen already loaded: 3x7 + 3x6 = 39 min of work
        rel = lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:05')
        lab.share_eta(rel, '08:05')
        wait = -(-39 // 2)
        self.assertEqual(rel.x_state, 'revised')
        self.assertEqual(rel.x_ready_by, t('08:00') + timedelta(minutes=wait + 7))
        self.assertGreater(rel.x_ready_by, rel.x_target_at)  # never promised an impossible 08:05
        self.assertIn('Revised collection time', lab.msgs(rel)[-1])
        lab.act('04_kitchen_accept', rel)  # revised orders stay in the kitchen queue
        self.assertEqual(rel.x_state, 'preparing')

    def test_s4b_kitchen_load_brings_release_forward(self):
        lab = self.lab
        for _ in range(2):
            lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:45').write({'x_state': 'preparing'})
        for state in ('cancelled', 'collected', 'ready'):  # not kitchen load
            lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:45').write({'x_state': state})
        lab.order([('Cheese & Tomato Panini', 1, [])], pickup='09:30')  # held, not yet load
        rel = lab.order([('Caffè Latte', 1, [])], pickup='08:45')
        lab.share_eta(rel, '08:30')
        # 14 min of work / 2 baristas = 7 min queue: 08:30 - 3 prep - 7 queue - 1 buffer
        self.assertEqual((rel.x_state, rel.x_release_at), ('held', t('08:19')))

    def test_s5_declined_location_uses_pickup_time(self):
        lab = self.lab
        rel = lab.order([('Cold Brew', 1, [])], pickup='08:30')
        self.assertFalse(rel.x_location_consent)
        self.assertEqual((rel.x_state, rel.x_target_at, rel.x_release_at), ('held', t('08:30'), t('08:28')))
        lab.tick_to('08:28')
        self.assertEqual(rel.x_state, 'released')

    def test_s6_every_release_traces_to_one_paid_order(self):
        lab = self.lab
        unpaid = lab.order([('Caffè Latte', 1, [])], pickup='08:30', paid=False)
        a = lab.order([('Cappuccino', 1, [])], pickup='08:30')
        b = lab.order([('Blueberry Muffin', 1, [])], pickup='08:30')
        a.x_pos_order_id.write({'state': 'done'})  # posting the session must not duplicate
        rels = lab.env['x_pickup_release'].search([])
        self.assertEqual(len(rels), 2)
        self.assertFalse(lab.env['x_pickup_release'].search([('x_pos_order_id', '=', unpaid.id)]))
        for rel in rels:
            self.assertIn(rel.x_pos_order_id.state, ('paid', 'done'))
        self.assertEqual(len(set(rels.mapped('x_name'))), 2)
        self.assertEqual(b.x_prep_minutes, 0)

    def test_s7_staff_override_with_audit(self):
        lab = self.lab
        rel = lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:40')
        lab.share_eta(rel, '08:25')
        self.assertEqual(rel.x_release_at, t('08:17'))
        rel.write({'x_release_at': t('08:10'), 'x_override_reason': 'Regular customer, always early'})
        lab.act('08_apply_override', rel)
        self.assertTrue(rel.x_override)
        self.assertEqual(rel.x_override_by.id, lab.env.uid)
        self.assertIn('Regular customer', lab.msgs(rel)[-1])
        lab.eta_event(rel, '08:05', '08:35')
        lab.tick_to('08:09')
        self.assertEqual((rel.x_state, rel.x_release_at), ('held', t('08:10')))  # ETA no longer moves it
        lab.tick_to('08:10')
        self.assertEqual(rel.x_state, 'released')

    def test_s7b_override_requires_reason(self):
        lab = self.lab
        rel = lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:40')
        with self.assertRaises(UserError):
            lab.act('08_apply_override', rel)

    def test_s9_withdraw_consent_deletes_eta_and_falls_back(self):
        lab = self.lab
        rel = lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:40')
        lab.share_eta(rel, '08:15')
        lab.eta_event(rel, '08:05', '08:20')
        lab.act('09_withdraw_consent', rel)
        self.assertFalse(rel.x_eta)
        self.assertFalse(lab.env['x_eta_event'].search([('x_release_id', '=', rel.id)]))
        self.assertEqual((rel.x_target_at, rel.x_release_at), (t('08:40'), t('08:32')))
        self.assertIn('consent withdrawn', lab.msgs(rel)[-1])

    def test_s6b_paid_state_without_payment_creates_no_release(self):
        lab = self.lab
        order = lab.order([('Americano', 1, [])], pickup='08:30', paid=False)
        order.write({'state': 'paid'})  # amount_paid still 0: nothing to trace to
        self.assertFalse(lab.env['x_pickup_release'].search([]))

    def test_quantity_multiplies_prep_time(self):
        rel = self.lab.order([('Americano', 2, [])], pickup='08:30')
        self.assertEqual(rel.x_prep_minutes, 4)

    def test_modifier_prep_deltas_feed_prep_time(self):
        rel = self.lab.order([('Caffè Latte', 1, ['Large 20oz', 'Extra espresso shot']),
                              ('Blueberry Muffin', 2, [])], pickup='08:30')
        self.assertEqual(rel.x_prep_minutes, 4)  # 180s + 15s + 20s = 215s -> 4 min; muffins 0
        self.assertEqual(rel.x_max_hold_minutes, 5)

    def test_messages_use_venue_timezone(self):
        lab = self.lab
        lab.cfg.write({'x_tz': 'America/New_York'})  # 12:11 UTC = 08:11 EDT
        lab.cfg.write({'x_now': datetime(2026, 10, 13, 12, 0)})
        rel = lab.order([('Caffè Latte', 1, [])], pickup='12:20')
        lab.share_eta(rel, '12:15')
        lab.tick_to('12:11')
        self.assertEqual(lab.msgs(rel)[-1], 'Released to kitchen at 08:11; ready by 08:14.')

    def test_no_arrival_time_left_in_chatter_after_withdrawal(self):
        lab = self.lab
        rel = lab.order([('Mocha Frost', 1, [])], pickup='08:40')
        lab.share_eta(rel, '08:10')
        lab.tick_to('08:04')
        lab.act('04_kitchen_accept', rel)
        lab.eta_event(rel, '08:05', '08:27')
        lab.tick_to('08:05')
        lab.act('09_withdraw_consent', rel)
        for eta in ('08:10', '08:27'):
            self.assertFalse([m for m in lab.msgs(rel) if eta in m], eta)

    def test_webhook_rejects_out_of_range_minutes(self):
        lab = self.lab
        rel = lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:40')
        rel.write({'x_location_consent': True})
        for bad in ({'minutes_away': 999}, {}):
            with self.assertRaises(UserError):
                run(CODE['10_webhook_eta'], '10', lab.env, rel, payload=bad)

    def test_webhook_eta_requires_consent(self):
        lab = self.lab
        rel = lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:40')
        run(CODE['10_webhook_eta'], '10', lab.env, rel, payload={'minutes_away': 10})
        self.assertFalse(rel.x_eta)
        rel.write({'x_location_consent': True})
        run(CODE['10_webhook_eta'], '10', lab.env, rel, payload={'minutes_away': 10})
        self.assertEqual((rel.x_eta, rel.x_release_at), (t('08:10'), t('08:02')))

    def test_kitchen_buttons_enforce_state_order(self):
        lab = self.lab
        rel = lab.order([('Cheese & Tomato Panini', 1, [])], pickup='08:40')
        for step in ('04_kitchen_accept', '05_kitchen_ready', '06_collected'):
            with self.assertRaises(UserError):
                lab.act(step, rel)
        lab.act('07_cancel', rel)
        self.assertEqual(rel.x_state, 'cancelled')


if __name__ == '__main__':
    unittest.main()
