import { formatPrice, round as roundValue } from "../util/format";
import * as fmt from "../util/format";
import type { Item } from "./item";
import { EventEmitter } from "events";

export class Cart extends EventEmitter {
  private items: Item[] = [];

  constructor(private readonly owner: string) {
    super();
  }

  add(item: Item): void {
    this.items.push(item);
    this.emit("added", item);
  }

  total(): number {
    const sum = this.items.reduce((acc, i) => acc + i.price, 0);
    return roundValue(sum);
  }

  describe(): string {
    const text = "call formatPrice(1) inside a string";
    return fmt.formatPrice(this.total()) + text;
  }
}

export function createCart(owner: string): Cart {
  return new Cart(owner);
}
