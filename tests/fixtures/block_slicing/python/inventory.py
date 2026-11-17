"""Inventory service: stock levels, reservations and restock planning."""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from shop.pricing import apply_discount
from shop.storage import StockStore

LOG = logging.getLogger(__name__)
DEFAULT_RESTOCK_THRESHOLD = 5


def audited(fn):
    """Logs every call of the decorated function."""
    def wrapper(*args, **kwargs):
        LOG.info("calling %s", fn.__name__)
        return fn(*args, **kwargs)
    return wrapper


@dataclass
class Reservation:
    sku: str
    quantity: int
    owner: Optional[str] = None


# Größe – ünïcödé 🚀 before the next block: line numbers must stay exact.
@dataclass
class Inventory:
    """In-memory stock levels backed by a StockStore."""

    store: StockStore
    levels: Dict[str, int] = field(default_factory=dict)
    reservations: List[Reservation] = field(default_factory=list)

    @property
    def total_units(self) -> int:
        return sum(self.levels.values())

    @audited
    def reserve(self, sku: str, quantity: int, owner: Optional[str] = None) -> Reservation:
        available = self.levels.get(sku, 0)
        if quantity > available:
            raise ValueError(f"only {available} units of {sku} left")
        self.levels[sku] = available - quantity
        reservation = Reservation(sku, quantity, owner)
        self.reservations.append(reservation)
        return reservation

    def release(self, reservation: Reservation) -> None:
        self.levels[reservation.sku] = self.levels.get(reservation.sku, 0) + reservation.quantity
        self.reservations.remove(reservation)

    @staticmethod
    def restock_quantity(current: int, threshold: int = DEFAULT_RESTOCK_THRESHOLD) -> int:
        if current >= threshold:
            return 0
        return math.ceil((threshold - current) * 1.5)

    def plan_restock(self) -> Dict[str, int]:
        # Nested helper: only SKUs below the threshold are planned.
        def below_threshold(sku: str) -> bool:
            return self.levels.get(sku, 0) < DEFAULT_RESTOCK_THRESHOLD

        plan = {}
        for sku in sorted(self.levels):
            if below_threshold(sku):
                plan[sku] = self.restock_quantity(self.levels[sku])
        return plan


async def sync_levels(inventory: Inventory, skus: List[str]) -> int:
    """Refreshes stock levels from the store concurrently."""
    results = await asyncio.gather(*(inventory.store.fetch_level(sku) for sku in skus))
    for sku, level in zip(skus, results):
        inventory.levels[sku] = level
    return len(results)


def discounted_value(inventory: Inventory, prices: Dict[str, float], pct: float) -> float:
    total = 0.0
    for sku, units in inventory.levels.items():
        total += apply_discount(prices.get(sku, 0.0), pct) * units
    return round(total, 2)


if __name__ == "__main__":
    print(Inventory.restock_quantity(2))
