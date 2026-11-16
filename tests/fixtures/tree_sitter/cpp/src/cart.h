#pragma once
#include <vector>

class Cart {
public:
    double total() const;

private:
    double sum() const;
    std::vector<double> prices_;
};
