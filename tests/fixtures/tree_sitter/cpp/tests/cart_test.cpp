#include "../src/cart.h"

int main() {
    Cart cart;
    return cart.total() >= 0 ? 0 : 1;
}
