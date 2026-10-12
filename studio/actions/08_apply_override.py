# Server action (button "Apply override") on x_pickup_release (acceptance check 5).
# Staff first enter x_release_at and x_override_reason on the form; tracking records old/new values.
cfg = env['x_venue_config'].search([], limit=1)
tz = timezone(cfg.x_tz or 'UTC')
hm = lambda d: d.replace(tzinfo=datetime.timezone.utc).astimezone(tz).strftime('%H:%M')
for rel in records:
    if rel.x_state != 'held':
        raise UserError('Override applies to held orders only (%s is %s).' % (rel.x_name, rel.x_state))
    if not rel.x_override_reason or not rel.x_release_at:
        raise UserError('Enter a release time and an override reason first.')
    rel.write({'x_override': True, 'x_override_by': env.uid})
    rel.message_post(body='Schedule overridden by %s: release at %s. Reason: %s' % (env.user.name, hm(rel.x_release_at), rel.x_override_reason))
