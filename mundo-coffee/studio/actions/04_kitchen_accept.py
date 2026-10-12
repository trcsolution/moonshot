# Server action (button "Accept") on x_pickup_release: kitchen starts preparing.
for rel in records:
    if rel.x_state not in ('released', 'revised'):
        raise UserError('Only released orders can be accepted (%s is %s).' % (rel.x_name, rel.x_state))
    rel.write({'x_state': 'preparing'})
