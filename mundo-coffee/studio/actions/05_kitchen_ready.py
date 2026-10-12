# Server action (button "Ready") on x_pickup_release: journey step 6, express pickup instruction.
for rel in records:
    if rel.x_state != 'preparing':
        raise UserError('Only orders in preparation can be marked ready (%s is %s).' % (rel.x_name, rel.x_state))
    rel.write({'x_state': 'ready'})
    rel.message_post(body='Order %s is ready. Use the express pickup lane and show order number %s.' % (rel.x_name, rel.x_pos_order_id.tracking_number or rel.x_name))
