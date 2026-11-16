#include "shop/pricing.h"
#include <cmath>

// double fake_from_comment() { return not_called(); }
namespace shop {

double apply_discount(double price, double pct) {
    const char* note = "double not_real() { call(); }";
    (void)note;
    return round2(price * (1 - pct / 100));
}

Rule::Rule(double pct) : pct_(pct) {}

double Rule::apply(double price) const {
    return apply_discount(price, pct_);
}

}  // namespace shop

int größe() { return 3; }
