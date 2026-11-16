package com.shop.cart;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.shop.pricing.PriceCalculator;
import org.junit.jupiter.api.Test;

class CartTest {
    @Test
    void totals() {
        Cart cart = new Cart();
        assertEquals(0.0, cart.total(10), 0.001);
        assertEquals(9.0, PriceCalculator.applyDiscount(10, 10), 0.001);
    }
}
