# Server action (button "Cancel") on x_pickup_release. The refund is done with the native POS refund.
for rel in records:
    if rel.x_state in ('collected', 'cancelled'):
        raise UserError('%s is already %s.' % (rel.x_name, rel.x_state))
    rel.write({'x_state': 'cancelled'})
    rel.message_post(body='Cancelled. Refund order %s through POS refund.' % (rel.x_pos_order_id.pos_reference or rel.x_pos_order_id.name))
