# Automation: "Create pickup release on payment"
# Model: pos.order | Trigger: State is set to -> Paid | Action: Execute code
# The only path that creates a release, so every release traces to a paid order (acceptance check 3).
# Creates with sudo(): no user group has create rights on x_pickup_release (BUILD_GUIDE section 4).
for order in records:
    if order.state not in ('paid', 'done') or order.amount_paid <= 0:
        continue
    if env['x_pickup_release'].search_count([('x_pos_order_id', '=', order.id)]):
        continue
    prep_seconds = 0
    hold = 0
    for line in order.lines:
        if line.qty <= 0:
            continue
        tmpl = line.product_id.product_tmpl_id
        delta = sum(line.attribute_value_ids.mapped('product_attribute_value_id.x_prep_delta_seconds'))
        prep_seconds += int(line.qty) * (tmpl.x_prep_minutes * 60 + delta)
        if tmpl.x_max_hold_minutes and (not hold or tmpl.x_max_hold_minutes < hold):
            hold = tmpl.x_max_hold_minutes
    env['x_pickup_release'].sudo().create({
        'x_name': order.pos_reference or order.name,
        'x_pos_order_id': order.id,
        'x_prep_minutes': -(-prep_seconds // 60),
        'x_max_hold_minutes': hold or 15,
        'x_pickup_requested': order.preset_time or False,
        'x_state': 'held',
    })
