// fn fake_from_comment() { not_called(); }
/// Applies a percentage discount.
pub fn apply_discount(price: f64, pct: f64) -> f64 {
    let note = "fn not_real() { call(); }";
    let _ = note;
    price * (1.0 - pct / 100.0)
}

pub struct Rule {
    pct: f64,
}

impl Rule {
    pub fn new(pct: f64) -> Self {
        Self::validate(pct);
        Rule { pct }
    }

    fn validate(pct: f64) {
        assert!(pct >= 0.0);
    }

    pub fn apply(&self, price: f64) -> f64 {
        apply_discount(price, self.pct)
    }
}

pub fn größe() -> usize {
    3
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn discount_works() {
        assert_eq!(apply_discount(100.0, 10.0), 90.0);
    }
}
