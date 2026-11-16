use shop::cart::Cart;

#[test]
fn empty_cart_total_is_zero() {
    let cart = Cart::new();
    assert_eq!(cart.total(), 0.0);
}
