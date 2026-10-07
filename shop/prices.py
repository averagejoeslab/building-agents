def total(items, discount=0):
    """Add up (price, quantity) pairs, then take off a percentage discount."""
    subtotal = sum(price * quantity for price, quantity in items)
    return round(subtotal - discount, 2)
