# Server action (button "Advance clock") on x_venue_config.
# Moves simulated time by x_tick_minutes, applies due ETA events, then touches x_clock_at
# on open releases so "Recalculate release" runs for each of them.
for cfg in records:
    new_now = (cfg.x_now or datetime.datetime.now()) + datetime.timedelta(minutes=cfg.x_tick_minutes or 1)
    cfg.write({'x_now': new_now})
    events = env['x_eta_event'].search([('x_applied', '=', False), ('x_at', '<=', new_now)], order='x_at')
    for ev in events:
        ev.x_release_id.write({'x_eta': ev.x_new_eta})
        ev.write({'x_applied': True})
    env['x_pickup_release'].search([
        ('x_state', 'in', ('held', 'released', 'revised', 'preparing', 'ready'))]).write({'x_clock_at': new_now})
