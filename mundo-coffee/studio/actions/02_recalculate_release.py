# Automation: "Recalculate release"
# Model: x_pickup_release | Trigger: On create and edit
# Trigger fields: x_eta, x_pickup_requested, x_location_consent, x_override, x_clock_at
# Action: Execute code. Never writes a trigger field, so it cannot re-trigger itself.
# Messages never include the customer's arrival time: chatter outlives a consent withdrawal.
cfg = env['x_venue_config'].search([], limit=1)
now = cfg.x_now or datetime.datetime.now()
cap = max(cfg.x_capacity or 1, 1)
buf = datetime.timedelta(minutes=cfg.x_buffer_minutes or 0)
tz = timezone(cfg.x_tz or 'UTC')
hm = lambda d: d.replace(tzinfo=datetime.timezone.utc).astimezone(tz).strftime('%H:%M')
open_states = ('held', 'released', 'revised', 'preparing', 'ready')
todo = records.filtered(lambda r: r.x_state in open_states)
todo = sorted(todo, key=lambda r: (r.x_state == 'held', (r.x_location_consent and r.x_eta) or r.x_pickup_requested or now))
for rel in todo:
    if rel.x_location_consent and rel.x_eta:
        target = rel.x_eta
    else:
        target = rel.x_pickup_requested or now
    prep = datetime.timedelta(minutes=rel.x_prep_minutes)
    hold = datetime.timedelta(minutes=rel.x_max_hold_minutes or 0)
    vals = {'x_target_at': target}
    msg = False
    if rel.x_state in ('held', 'released'):
        others = env['x_pickup_release'].search([
            ('x_state', 'in', ('released', 'revised', 'preparing')), ('id', '!=', rel.id)])
        load = sum(others.mapped('x_prep_minutes'))
        wait = datetime.timedelta(minutes=-(-load // cap))
        if rel.x_override and rel.x_release_at:
            release_at = rel.x_release_at
        else:
            release_at = target - prep - wait - buf
        if release_at > now:
            vals['x_release_at'] = release_at
            if rel.x_state == 'released':
                vals['x_state'] = 'held'
                msg = 'Release postponed to %s: arrival moved later and the kitchen had not started.' % hm(release_at)
        elif rel.x_state == 'held':
            ready_by = now + wait + prep
            vals.update({'x_release_at': now, 'x_ready_by': ready_by})
            if ready_by > target:
                vals['x_state'] = 'revised'
                msg = 'Kitchen cannot meet the requested time. Revised collection time %s sent to customer.' % hm(ready_by)
            else:
                vals['x_state'] = 'released'
                msg = 'Released to kitchen at %s; ready by %s.' % (hm(now), hm(ready_by))
    elif rel.x_state in ('preparing', 'ready'):
        if rel.x_ready_by and not rel.x_late_alert and target > rel.x_ready_by + hold:
            vals['x_late_alert'] = True
            msg = 'LATE ALERT: customer now due after the %s min hold window for an order ready at %s. Decide: hold, remake or contact customer.' % (rel.x_max_hold_minutes, hm(rel.x_ready_by))
    rel.write(vals)
    if msg:
        rel.message_post(body=msg)
