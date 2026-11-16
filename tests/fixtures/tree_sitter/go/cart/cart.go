package cart

import (
	"fmt"

	"example.com/shop/pricing"
	pr "example.com/shop/pricing"
)

type Cart struct {
	prices []float64
}

func New() *Cart {
	return &Cart{}
}

func (c *Cart) Total() float64 {
	discounted := pricing.ApplyDiscount(c.sum(), 10)
	return pr.AddTax(discounted)
}

func (c *Cart) sum() float64 {
	total := 0.0
	for _, p := range c.prices {
		total += p
	}
	return total
}

func (c *Cart) String() string {
	return fmt.Sprintf("cart(%d)", len(c.prices))
}
