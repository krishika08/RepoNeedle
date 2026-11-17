package inventory

import (
	"errors"
	"fmt"
	"math"
	"sort"

	"example.com/shop/pricing"
)

// DefaultThreshold is the restock threshold.
const DefaultThreshold = 5

// Reservation holds reserved units of one SKU.
type Reservation struct {
	SKU      string
	Quantity int
	Owner    string
}

// Größe – ünïcödé 🚀 before the next block: line numbers must stay exact.
// Inventory tracks stock levels.
type Inventory struct {
	levels       map[string]int
	reservations []Reservation
}

// New returns an empty inventory.
func New() *Inventory {
	return &Inventory{levels: map[string]int{}}
}

// Reserve takes units out of stock.
func (inv *Inventory) Reserve(sku string, quantity int, owner string) (Reservation, error) {
	available := inv.levels[sku]
	if quantity > available {
		return Reservation{}, errors.New(fmt.Sprintf("only %d units of %s left", available, sku))
	}
	inv.levels[sku] = available - quantity
	r := Reservation{SKU: sku, Quantity: quantity, Owner: owner}
	inv.reservations = append(inv.reservations, r)
	return r, nil
}

// PlanRestock lists the SKUs below the threshold.
func (inv *Inventory) PlanRestock() map[string]int {
	restockQuantity := func(current int) int {
		return int(math.Ceil(float64(DefaultThreshold-current) * 1.5))
	}
	skus := make([]string, 0, len(inv.levels))
	for sku := range inv.levels {
		skus = append(skus, sku)
	}
	sort.Strings(skus)
	plan := map[string]int{}
	for _, sku := range skus {
		if inv.levels[sku] < DefaultThreshold {
			plan[sku] = restockQuantity(inv.levels[sku])
		}
	}
	return plan
}

var formatLevel = func(sku string, units int) string {
	return fmt.Sprintf("%s=%d", sku, units)
}

// DiscountedValue prices every unit with a discount.
func DiscountedValue(inv *Inventory, prices map[string]float64, pct float64) float64 {
	total := 0.0
	for sku, units := range inv.levels {
		total += pricing.ApplyDiscount(prices[sku], pct) * float64(units)
	}
	return total
}
