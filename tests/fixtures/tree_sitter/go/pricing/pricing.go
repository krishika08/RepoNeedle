// Package pricing applies discounts.
// func FakeFromComment() { notCalled() }
package pricing

const banner = "func NotReal() { call() }"

// Rule is a percentage discount.
type Rule struct {
	Pct float64
}

// ApplyDiscount returns the discounted price.
func ApplyDiscount(price, pct float64) float64 {
	return round2(price * (1 - pct/100))
}

func (r *Rule) Apply(price float64) float64 {
	return ApplyDiscount(price, r.Pct)
}

func round2(v float64) float64 {
	return float64(int(v*100+0.5)) / 100
}

func Größe() int { return len(banner) }
