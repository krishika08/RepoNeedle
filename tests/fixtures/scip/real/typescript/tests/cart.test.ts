import { createCart } from "../src/models/cart";
import { makeItem } from "../src/models/item";

describe("cart", () => {
  it("totals items", () => {
    const cart = createCart("ann");
    cart.add(makeItem("a", 1.005));
    expect(cart.total()).toBe(1.01);
  });
});
