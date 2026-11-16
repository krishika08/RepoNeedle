#include "cart.h"
#include "shop/pricing.h"
#include <cmath>

double Cart::total() const {
    shop::Rule rule(10);
    auto* extra = new shop::Rule(5);
    double t = rule.apply(sum()) + shop::apply_discount(1.0, 2.0);
    delete extra;
    return std::round(t);
}

double Cart::sum() const {
    double s = 0;
    for (double p : prices_) {
        s += p;
    }
    return s;
}
