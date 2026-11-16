use crate::pricing::{apply_discount, Rule};
use crate::util;

pub struct Cart {
    prices: Vec<f64>,
}

impl Cart {
    pub fn new() -> Self {
        Cart { prices: Vec::new() }
    }

    pub fn total(&self) -> f64 {
        fn local_helper(x: f64) -> f64 {
            x
        }
        let rule = Rule::new(10.0);
        let discounted = rule.apply(self.sum());
        let direct = crate::pricing::apply_discount(discounted, 0.0);
        println!("{}", hidden_in_macro());
        util::round2(local_helper(direct)) + apply_discount(0.0, 0.0)
    }

    fn sum(&self) -> f64 {
        self.prices.iter().sum()
    }
}
