#pragma once

namespace shop {

double apply_discount(double price, double pct);

class Rule {
public:
    explicit Rule(double pct);
    double apply(double price) const;

    template <typename T>
    T clamp(T value) const {
        return value < 0 ? T(0) : value;
    }

private:
    double pct_;
};

inline double round2(double v) {
    return static_cast<long>(v * 100 + 0.5) / 100.0;
}

}  // namespace shop
