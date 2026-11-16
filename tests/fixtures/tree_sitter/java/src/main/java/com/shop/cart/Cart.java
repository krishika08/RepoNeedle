package com.shop.cart;

import com.shop.pricing.PriceCalculator;
import static com.shop.pricing.PriceCalculator.applyDiscount;
import java.util.ArrayList;
import java.util.List;
import java.util.function.*;

public class Cart {
    private final List<Double> prices = new ArrayList<>();

    public Cart() {
        this(0.0);
    }

    public Cart(double initial) {
        prices.add(initial);
    }

    public double total(double pct) {
        double sum = sum();
        return new PriceCalculator().withTax(applyDiscount(sum, pct));
    }

    private double sum() {
        double s = 0;
        for (double p : prices) {
            s += p;
        }
        return s;
    }

    static class Line {
        double price() {
            return 0;
        }
    }

    interface Visitor {
        void visit(Line line);
    }

    Runnable listener() {
        return new Runnable() {
            public void run() {
                sum();
            }
        };
    }
}
