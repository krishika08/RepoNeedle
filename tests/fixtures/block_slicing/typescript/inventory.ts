import { EventEmitter } from "events";
import { applyDiscount, roundPrice } from "../pricing/discount";
import type { StockStore } from "../storage/store";
import * as log from "../util/log";

export const DEFAULT_THRESHOLD = 5;

export interface Reservation {
  sku: string;
  quantity: number;
  owner?: string;
}

function Audited(target: unknown, key: string): void {
  log.info(`decorating ${key}`);
}

// Größe – ünïcödé 🚀 before the next block: line numbers must stay exact.
/** In-memory stock levels backed by a StockStore. */
export class Inventory extends EventEmitter {
  private levels = new Map<string, number>();
  private reservations: Reservation[] = [];

  constructor(private readonly store: StockStore) {
    super();
  }

  get totalUnits(): number {
    let total = 0;
    this.levels.forEach((units) => (total += units));
    return total;
  }

  @Audited
  reserve(sku: string, quantity: number, owner?: string): Reservation {
    const available = this.levels.get(sku) ?? 0;
    if (quantity > available) {
      throw new Error(`only ${available} units of ${sku} left`);
    }
    this.levels.set(sku, available - quantity);
    const reservation = { sku, quantity, owner };
    this.reservations.push(reservation);
    this.emit("reserved", reservation);
    return reservation;
  }

  release = (reservation: Reservation): void => {
    const current = this.levels.get(reservation.sku) ?? 0;
    this.levels.set(reservation.sku, current + reservation.quantity);
  };

  planRestock(): Map<string, number> {
    function restockQuantity(current: number): number {
      return Math.ceil((DEFAULT_THRESHOLD - current) * 1.5);
    }
    const plan = new Map<string, number>();
    for (const [sku, units] of this.levels) {
      if (units < DEFAULT_THRESHOLD) {
        plan.set(sku, restockQuantity(units));
      }
    }
    return plan;
  }
}

export const discountedValue = (inventory: Inventory, prices: Map<string, number>, pct: number): number => {
  let total = 0;
  for (const sku of prices.keys()) {
    total += applyDiscount(prices.get(sku) ?? 0, pct);
  }
  return roundPrice(total);
};

export async function syncLevels(inventory: Inventory, skus: string[]): Promise<number> {
  const results = await Promise.all(skus.map((sku) => inventory["store"].fetchLevel(sku)));
  return results.length;
}

export namespace InventoryStats {
  export function averageUnits(inventory: Inventory, count: number): number {
    return count === 0 ? 0 : inventory.totalUnits / count;
  }
}
