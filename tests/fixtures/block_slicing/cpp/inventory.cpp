#include "shop/inventory.h"
#include "shop/pricing.h"

#include <cmath>
#include <map>
#include <stdexcept>
#include <string>

namespace shop {

constexpr int kDefaultThreshold = 5;

template <typename T>
T clamp_units(T value, T low, T high) {
    if (value < low) {
        return low;
    }
    return value > high ? high : value;
}

// Größe – ünïcödé 🚀 before the next block: line numbers must stay exact.
class Inventory {
public:
    Inventory() = default;

    int total_units() const {
        int total = 0;
        for (const auto& entry : levels_) {
            total += entry.second;
        }
        return total;
    }

    Reservation reserve(const std::string& sku, int quantity);
    std::map<std::string, int> plan_restock() const;

private:
    std::map<std::string, int> levels_;
};

/// Takes units out of stock.
Reservation Inventory::reserve(const std::string& sku, int quantity) {
    const int available = levels_[sku];
    if (quantity > available) {
        throw std::runtime_error("only " + std::to_string(available) + " units of " + sku + " left");
    }
    levels_[sku] = available - quantity;
    return Reservation{sku, quantity};
}

std::map<std::string, int> Inventory::plan_restock() const {
    std::map<std::string, int> plan;
    for (const auto& entry : levels_) {
        if (entry.second < kDefaultThreshold) {
            plan[entry.first] = static_cast<int>(std::ceil((kDefaultThreshold - entry.second) * 1.5));
        }
    }
    return plan;
}

}  // namespace shop

extern "C" {
int inventory_restock_quantity(int current) {
    return shop::clamp_units(kDefaultThreshold - current, 0, 100);
}
}
