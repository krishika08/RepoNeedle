"""
Deterministic fixture repository for the index-equivalence harness (tests/index_equivalence.py).

It is small enough to index in well under a second, but exercises every index:
- Python packages with absolute and relative imports, classes, methods, call chains and tests;
- duplicate function names in different modules (`normalize`, `load_config`), for the function graph's
  global-uniqueness resolution and first/last-wins maps;
- duplicate module stems in different packages (`utils`);
- TypeScript, Go (`go.mod`), Rust (`Cargo.toml`) and Java sources;
- Markdown, YAML, TOML and JSON documents;
- Unicode identifiers and content (non-ASCII letters, CJK, emoji);
- one large generated module (still far below the default 500,000-byte file-size limit).
"""

from pathlib import Path
from typing import Dict


def _large_module(n_funcs: int = 120) -> str:
    out = ['"""Generated catalogue of pricing rules (large-file fixture)."""', "", "from shop.pricing import apply_discount", ""]
    for i in range(n_funcs):
        out += [
            f"def rule_{i:04d}(amount, quantity):",
            f'    """Pricing rule {i}: tiered discount for bucket {i % 17}."""',
            f"    if quantity > {i % 9 + 1}:",
            f"        return apply_discount(amount, {i % 23 + 1})",
            f"    return amount * {1 + (i % 5) / 10:.1f}",
            "",
        ]
    return "\n".join(out) + "\n"


FILES: Dict[str, str] = {
    "README.md": (
        "# Shop service\n\nA small shop with a cart, pricing rules, inventory and an HTTP API.\n\n"
        "Run the tests with `pytest`. Configuration lives in `config/settings.yaml`.\n"
    ),
    "pyproject.toml": '[project]\nname = "shop"\nversion = "0.1.0"\n',
    "config/settings.yaml": "currency: EUR\ntax_rate: 0.2\nwarehouse: north\n",
    "package.json": '{"name": "shop-web", "version": "1.0.0", "dependencies": {"left-pad": "1.3.0"}}\n',
    "shop/__init__.py": '"""Shop package."""\n\nfrom shop.cart import Cart\n',
    "shop/cart.py": (
        "from shop.pricing import price_for, apply_discount\n"
        "from shop.inventory import Inventory\n"
        "from shop.utils.strings import normalize\n\n\n"
        "class Cart:\n"
        '    """Shopping cart holding line items."""\n\n'
        "    def __init__(self, inventory=None):\n"
        "        self.items = {}\n"
        "        self.inventory = inventory or Inventory()\n\n"
        "    def add_item(self, sku, quantity=1):\n"
        "        sku = normalize(sku)\n"
        "        self.inventory.reserve(sku, quantity)\n"
        "        self.items[sku] = self.items.get(sku, 0) + quantity\n\n"
        "    def remove_item(self, sku):\n"
        "        self.items.pop(normalize(sku), None)\n\n"
        "    def total(self, coupon=None):\n"
        "        amount = sum(price_for(sku) * qty for sku, qty in self.items.items())\n"
        "        return apply_discount(amount, coupon) if coupon else amount\n"
    ),
    "shop/pricing.py": (
        "from shop.utils.config import load_config\n\n"
        "PRICES = {'APPLE': 3, 'PEAR': 4}\n\n\n"
        "def price_for(sku):\n"
        "    return PRICES.get(sku, 0) * (1 + load_config()['tax_rate'])\n\n\n"
        "def apply_discount(amount, percent):\n"
        "    if percent <= 0:\n"
        "        raise ValueError('discount must be positive')\n"
        "    return round(amount * (100 - percent) / 100, 2)\n"
    ),
    "shop/inventory.py": (
        "from .utils.strings import normalize\n\n\n"
        "class OutOfStock(Exception):\n"
        "    pass\n\n\n"
        "class Inventory:\n"
        "    def __init__(self):\n"
        "        self.stock = {'APPLE': 10, 'PEAR': 2}\n\n"
        "    def reserve(self, sku, quantity):\n"
        "        sku = normalize(sku)\n"
        "        if self.stock.get(sku, 0) < quantity:\n"
        "            raise OutOfStock(sku)\n"
        "        self.stock[sku] -= quantity\n"
    ),
    "shop/utils/__init__.py": "",
    "shop/utils/strings.py": (
        "def normalize(value):\n"
        "    return value.strip().upper()\n\n\n"
        "def slugify(value):\n"
        "    return normalize(value).lower().replace(' ', '-')\n"
    ),
    "shop/utils/config.py": (
        "import json\n\n\n"
        "def load_config(path='config/settings.json'):\n"
        "    return {'tax_rate': 0.2, 'currency': 'EUR'}\n"
    ),
    "shop/api/routes.py": (
        "from shop.cart import Cart\n"
        "from shop.pricing import apply_discount\n\n\n"
        "def checkout_handler(request):\n"
        "    cart = Cart()\n"
        "    for line in request['lines']:\n"
        "        cart.add_item(line['sku'], line['qty'])\n"
        "    return {'total': cart.total(request.get('coupon'))}\n\n\n"
        "def health_handler(request):\n"
        "    return {'status': 'ok'}\n"
    ),
    "shop/rules_catalogue.py": _large_module(),
    "legacy/utils.py": (
        "def normalize(value):\n"
        "    '''Legacy normaliser kept for the old importer.'''\n"
        "    return value.lower()\n\n\n"
        "def load_config():\n"
        "    return {}\n"
    ),
    "legacy/importer.py": (
        "from legacy.utils import normalize\n\n\n"
        "def import_rows(rows):\n"
        "    return [normalize(r) for r in rows]\n"
    ),
    "i18n/übersetzung.py": (
        "# -*- coding: utf-8 -*-\n"
        '"""Übersetzungen und Größenangaben — 翻訳テーブル 🛒."""\n\n'
        "GRÖSSEN = {'klein': 'S', 'groß': 'L'}\n\n\n"
        "def größe_für(artikel):\n"
        "    return GRÖSSEN.get(artikel, 'M')\n\n\n"
        "def 翻訳(text):\n"
        "    return text\n"
    ),
    "tests/test_cart.py": (
        "import pytest\n\n"
        "from shop.cart import Cart\n"
        "from shop.inventory import OutOfStock\n\n\n"
        "def test_add_item_updates_total():\n"
        "    cart = Cart()\n"
        "    cart.add_item('apple', 2)\n"
        "    assert cart.total() > 0\n\n\n"
        "def test_out_of_stock_raises():\n"
        "    cart = Cart()\n"
        "    with pytest.raises(OutOfStock):\n"
        "        cart.add_item('pear', 99)\n"
    ),
    "tests/test_pricing.py": (
        "import pytest\n\n"
        "from shop.pricing import apply_discount, price_for\n\n\n"
        "def test_apply_discount():\n"
        "    assert apply_discount(100, 10) == 90\n\n\n"
        "def test_negative_discount_rejected():\n"
        "    with pytest.raises(ValueError):\n"
        "        apply_discount(100, -1)\n"
    ),
    "tests/test_routes.py": (
        "from shop.api.routes import checkout_handler\n\n\n"
        "def test_checkout_handler():\n"
        "    assert 'total' in checkout_handler({'lines': [{'sku': 'apple', 'qty': 1}]})\n"
    ),
    "web/src/api.ts": (
        "import { formatPrice } from './format';\n\n"
        "export async function fetchCart(id: string): Promise<number> {\n"
        "  const res = await fetch(`/cart/${id}`);\n"
        "  return formatPrice(await res.json());\n"
        "}\n"
    ),
    "web/src/format.ts": (
        "export function formatPrice(value: number): number {\n"
        "  return Math.round(value * 100) / 100;\n"
        "}\n\n"
        "export function normalize(value: string): string {\n"
        "  return value.trim();\n"
        "}\n"
    ),
    "web/src/cart.test.ts": (
        "import { fetchCart } from './api';\n\n"
        "test('fetchCart returns a number', async () => {\n"
        "  expect(typeof (await fetchCart('1'))).toBe('number');\n"
        "});\n"
    ),
    "svc/go.mod": "module example.com/svc\n\ngo 1.21\n",
    "svc/main.go": (
        "package main\n\n"
        'import "example.com/svc/stock"\n\n'
        "func main() {\n"
        "\tstock.Reserve(\"APPLE\", 1)\n"
        "}\n"
    ),
    "svc/stock/stock.go": (
        "package stock\n\n"
        "func Reserve(sku string, qty int) bool {\n"
        "\treturn qty > 0\n"
        "}\n"
    ),
    "engine/Cargo.toml": '[package]\nname = "price-engine"\nversion = "0.1.0"\n',
    "engine/src/lib.rs": (
        "pub mod rules;\n\n"
        "pub fn quote(amount: f64) -> f64 {\n"
        "    rules::apply(amount)\n"
        "}\n"
    ),
    "engine/src/rules.rs": "pub fn apply(amount: f64) -> f64 {\n    amount * 0.9\n}\n",
    "java/src/main/java/shop/Checkout.java": (
        "package shop;\n\n"
        "public class Checkout {\n"
        "    public double total(double amount) {\n"
        "        return Discount.apply(amount);\n"
        "    }\n"
        "}\n"
    ),
    "java/src/main/java/shop/Discount.java": (
        "package shop;\n\n"
        "public class Discount {\n"
        "    public static double apply(double amount) {\n"
        "        return amount * 0.95;\n"
        "    }\n"
        "}\n"
    ),
    "docs/ARCHITECTURE.md": (
        "# Architecture\n\nThe cart calls pricing and inventory. The API layer exposes `checkout_handler`.\n"
        "Legacy import code still uses its own `normalize`.\n"
    ),
}


def write_files(root: Path, files: Dict[str, str]) -> Path:
    """Writes ``files`` (relative POSIX path -> text) under ``root`` as UTF-8 with LF line endings."""
    for rel, text in files.items():
        target = root.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return root
