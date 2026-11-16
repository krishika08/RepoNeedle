from shop.pricing import Rule, apply_discount


def check_rule():
    rule = Rule(10)
    assert rule.apply(100) == apply_discount(100, 10)
