package pricing

// AddTax adds 8% sales tax.
func AddTax(v float64) float64 {
	return round2(v * 1.08)
}
