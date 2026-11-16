import { createCart } from "../models/cart";
import { label } from "../util/format";

export function CartView({ owner }: { owner: string }) {
  const cart = createCart(owner);
  return <div title={label(owner)}>{cart.describe()}</div>;
}

export const Größe = (): string => label("ü");
