"""Pricing helpers (Python stays on the ast extractor)."""
from shop.util import round2


def apply_discount(price, pct):
    return round2(price * (1 - pct / 100))


class Rule:
    def __init__(self, pct):
        self.pct = pct

    def apply(self, price):
        return apply_discount(price, self.pct)
