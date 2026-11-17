export interface Item {
  sku: string;
  price: number;
}

export function makeItem(sku: string, price: number): Item {
  return { sku, price };
}
