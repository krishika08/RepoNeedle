package cart

import "testing"

func TestTotal(t *testing.T) {
	c := New()
	if c.Total() != 0 {
		t.Fatalf("unexpected total")
	}
}
