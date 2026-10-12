# Server action (button "Collected") on x_pickup_release: journey step 7.
# Sale, inventory and accounting reconcile through the native POS session close.
for rel in records:
    if rel.x_state != 'ready':
        raise UserError('Only ready orders can be collected (%s is %s).' % (rel.x_name, rel.x_state))
    rel.write({'x_state': 'collected'})
