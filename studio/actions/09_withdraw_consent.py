# Server action (button "Withdraw location consent") on x_pickup_release.
# x_eta is deliberately NOT tracked, so clearing it leaves no ETA history in the chatter.
cfg = env['x_venue_config'].search([], limit=1)
tz = timezone(cfg.x_tz or 'UTC')
hm = lambda d: d.replace(tzinfo=datetime.timezone.utc).astimezone(tz).strftime('%H:%M')
for rel in records:
    if not rel.x_pickup_requested:
        raise UserError('Set a pickup time before withdrawing consent, so the order still has a target.')
    rel.write({'x_location_consent': False, 'x_eta': False})
    env['x_eta_event'].sudo().search([('x_release_id', '=', rel.id)]).unlink()  # staff have no rights on simulator data
    rel.message_post(body='Location consent withdrawn. Arrival data deleted; using pickup time %s.' % hm(rel.x_pickup_requested))
