# Optional (WhatsApp spike / external simulator). Automation on x_pickup_release, Trigger: On webhook.
# Record getter: model.search([('x_name', '=', payload.get('order_ref'))], limit=1)
# Payload example: {"order_ref": "Order 00001-001-0001", "minutes_away": 5}
cfg = env['x_venue_config'].search([], limit=1)
now = cfg.x_now or datetime.datetime.now()
minutes = int(payload.get('minutes_away', -1))
if minutes < 0 or minutes > 120:
    raise UserError('minutes_away must be between 0 and 120')
for rel in records:
    if not rel.x_location_consent:
        continue
    rel.write({'x_eta': now + datetime.timedelta(minutes=minutes)})
