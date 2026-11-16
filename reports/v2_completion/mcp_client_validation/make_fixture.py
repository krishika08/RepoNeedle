"""
Create the disposable "shopcart" fixture repository used for the MCP client validation.

Usage:
    python make_fixture.py <target-directory>

The target must not exist yet (or be empty). The fixture contains only synthetic code:
    shopcart/pricing.py    utility module (discounts, tax, rounding)
    shopcart/cart.py       application module; imports shopcart.pricing
    shopcart/checkout.py   application module; imports shopcart.cart and shopcart.pricing
    shopcart/inventory.py  unrelated module (no dependency on pricing), used as a control
    tests/test_pricing.py, tests/test_cart.py, tests/test_checkout.py

Dependency chain: pricing.py <- cart.py <- checkout.py; tests import the modules they cover.
Known defect kept on purpose for the coding-workflow scenario: apply_discount() accepts
percentages above 100, which makes totals negative.
"""

import os
import sys
from textwrap import dedent

FILES = {
    "README.md": """
        # shopcart (synthetic fixture)

        A tiny shopping-cart library used to validate RepoNeedle's MCP server inside real coding
        clients. It contains no real data.

        Run the tests with `python -m pytest -q`.
    """,
    "shopcart/__init__.py": """
        \"\"\"Synthetic shopping-cart package for MCP client validation.\"\"\"
    """,
    "shopcart/pricing.py": """
        \"\"\"Pricing utilities: discounts, sales tax and currency rounding.\"\"\"

        TAX_RATE = 0.08


        def round_currency(amount: float) -> float:
            \"\"\"Round a monetary amount to cents.\"\"\"
            return round(amount + 1e-9, 2)


        def apply_discount(price: float, percent: float) -> float:
            \"\"\"Return the price after a percentage discount.\"\"\"
            if percent < 0:
                raise ValueError("discount percent cannot be negative")
            return round_currency(price * (1 - percent / 100))


        def add_tax(amount: float, rate: float = TAX_RATE) -> float:
            \"\"\"Return the amount including sales tax.\"\"\"
            return round_currency(amount * (1 + rate))
    """,
    "shopcart/cart.py": """
        \"\"\"Shopping cart that totals line items using the pricing utilities.\"\"\"

        from dataclasses import dataclass, field
        from typing import List

        from shopcart.pricing import add_tax, apply_discount, round_currency


        @dataclass
        class LineItem:
            sku: str
            unit_price: float
            quantity: int = 1


        @dataclass
        class Cart:
            items: List[LineItem] = field(default_factory=list)

            def add_item(self, sku: str, unit_price: float, quantity: int = 1) -> None:
                if quantity <= 0:
                    raise ValueError("quantity must be positive")
                self.items.append(LineItem(sku, unit_price, quantity))

            def subtotal(self) -> float:
                return round_currency(sum(i.unit_price * i.quantity for i in self.items))

            def total(self, discount_percent: float = 0.0) -> float:
                \"\"\"Subtotal, minus the discount, plus sales tax.\"\"\"
                return add_tax(apply_discount(self.subtotal(), discount_percent))
    """,
    "shopcart/checkout.py": """
        \"\"\"Checkout flow: validates coupon codes and produces a receipt.\"\"\"

        from shopcart.cart import Cart
        from shopcart.pricing import TAX_RATE

        COUPONS = {"WELCOME10": 10, "HALFOFF": 50, "STAFF": 30}


        def coupon_percent(code: str) -> float:
            if not code:
                return 0.0
            try:
                return float(COUPONS[code.strip().upper()])
            except KeyError:
                raise ValueError(f"unknown coupon code: {code}")


        def checkout(cart: Cart, coupon: str = "") -> dict:
            percent = coupon_percent(coupon)
            return {
                "items": len(cart.items),
                "subtotal": cart.subtotal(),
                "discount_percent": percent,
                "tax_rate": TAX_RATE,
                "total": cart.total(percent),
            }
    """,
    "shopcart/inventory.py": """
        \"\"\"Warehouse stock levels. Independent of pricing.\"\"\"

        STOCK = {"apple": 12, "pear": 0, "melon": 3}


        def in_stock(sku: str) -> bool:
            return STOCK.get(sku, 0) > 0


        def reserve(sku: str, quantity: int) -> None:
            available = STOCK.get(sku, 0)
            if quantity > available:
                raise ValueError(f"only {available} of {sku} available")
            STOCK[sku] = available - quantity
    """,
    "tests/__init__.py": "",
    "tests/test_pricing.py": """
        import pytest

        from shopcart.pricing import add_tax, apply_discount, round_currency


        def test_round_currency():
            assert round_currency(1.005) == 1.01


        def test_apply_discount():
            assert apply_discount(200.0, 10) == 180.0


        def test_negative_discount_rejected():
            with pytest.raises(ValueError):
                apply_discount(10.0, -5)


        def test_add_tax():
            assert add_tax(100.0) == 108.0
    """,
    "tests/test_cart.py": """
        import pytest

        from shopcart.cart import Cart


        def test_subtotal_and_total():
            cart = Cart()
            cart.add_item("apple", 2.50, 4)
            assert cart.subtotal() == 10.0
            assert cart.total() == 10.8
            assert cart.total(discount_percent=50) == 5.4


        def test_quantity_must_be_positive():
            with pytest.raises(ValueError):
                Cart().add_item("apple", 1.0, 0)
    """,
    "tests/test_checkout.py": """
        import pytest

        from shopcart.cart import Cart
        from shopcart.checkout import checkout


        def test_checkout_with_coupon():
            cart = Cart()
            cart.add_item("melon", 20.0)
            receipt = checkout(cart, "welcome10")
            assert receipt["discount_percent"] == 10.0
            assert receipt["total"] == 19.44


        def test_unknown_coupon():
            with pytest.raises(ValueError):
                checkout(Cart(), "BOGUS")
    """,
}


def main(target: str) -> None:
    if os.path.exists(target) and os.listdir(target):
        sys.exit(f"{target} exists and is not empty")
    for rel, body in FILES.items():
        path = os.path.join(target, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        text = dedent(body).lstrip("\n")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print(f"Created fixture with {len(FILES)} files in {os.path.abspath(target)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
