package com.shop.pricing;

/**
 * Pricing rules. public void fakeFromJavadoc() { notCalled(); }
 */
public class PriceCalculator {
    private static final String NOTE = "new Fake().call()";

    public static double applyDiscount(double price, double pct) {
        return round(price * (1 - pct / 100));
    }

    public double withTax(double value) {
        return round(value * 1.08);
    }

    private static double round(double v) {
        return Math.round(v * 100) / 100.0;
    }

    double größe() {
        return NOTE.length();
    }
}
