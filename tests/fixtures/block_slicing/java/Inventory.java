package com.shop.inventory;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import com.shop.pricing.PriceCalculator;

// Größe – ünïcödé 🚀 before the next block: line numbers must stay exact.
/**
 * In-memory stock levels.
 */
@Service
public class Inventory {
    public static final int DEFAULT_THRESHOLD = 5;

    private final Map<String, Integer> levels = new HashMap<>();
    private final List<Reservation> reservations = new ArrayList<>();

    /** Reserved units of one SKU. */
    public static final class Reservation {
        final String sku;
        final int quantity;

        Reservation(String sku, int quantity) {
            this.sku = sku;
            this.quantity = quantity;
        }
    }

    public Inventory() {
    }

    /**
     * Takes units out of stock.
     */
    @Transactional
    public Reservation reserve(String sku, int quantity) {
        int available = levels.getOrDefault(sku, 0);
        if (quantity > available) {
            throw new IllegalStateException("only " + available + " units of " + sku + " left");
        }
        levels.put(sku, available - quantity);
        Reservation reservation = new Reservation(sku, quantity);
        reservations.add(reservation);
        return reservation;
    }

    public Map<String, Integer> planRestock() {
        Map<String, Integer> plan = new TreeMap<>();
        for (Map.Entry<String, Integer> entry : levels.entrySet()) {
            if (entry.getValue() < DEFAULT_THRESHOLD) {
                plan.put(entry.getKey(), restockQuantity(entry.getValue()));
            }
        }
        return plan;
    }

    static int restockQuantity(int current) {
        return (int) Math.ceil((DEFAULT_THRESHOLD - current) * 1.5);
    }

    public double discountedValue(Map<String, Double> prices, double pct) {
        double total = 0;
        for (Map.Entry<String, Integer> entry : levels.entrySet()) {
            total += PriceCalculator.applyDiscount(prices.getOrDefault(entry.getKey(), 0.0), pct) * entry.getValue();
        }
        return total;
    }
}
