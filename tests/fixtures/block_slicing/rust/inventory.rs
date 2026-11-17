use std::collections::HashMap;
use std::fmt;

use crate::pricing::apply_discount;

pub const DEFAULT_THRESHOLD: u32 = 5;

/// Reserved units of one SKU.
#[derive(Debug, Clone, PartialEq)]
pub struct Reservation {
    pub sku: String,
    pub quantity: u32,
}

// Größe – ünïcödé 🚀 before the next block: line numbers must stay exact.
/// In-memory stock levels.
#[derive(Debug, Default)]
pub struct Inventory {
    levels: HashMap<String, u32>,
    reservations: Vec<Reservation>,
}

pub trait Restock {
    fn restock_quantity(&self, current: u32) -> u32;
}

impl Inventory {
    /// Creates an empty inventory.
    pub fn new() -> Self {
        Self::default()
    }

    /// Takes units out of stock.
    #[must_use = "the reservation must be released"]
    pub fn reserve(&mut self, sku: &str, quantity: u32) -> Result<Reservation, String> {
        let available = *self.levels.get(sku).unwrap_or(&0);
        if quantity > available {
            return Err(format!("only {} units of {} left", available, sku));
        }
        self.levels.insert(sku.to_string(), available - quantity);
        let reservation = Reservation { sku: sku.to_string(), quantity };
        self.reservations.push(reservation.clone());
        Ok(reservation)
    }

    pub fn plan_restock(&self) -> HashMap<String, u32> {
        fn below_threshold(units: u32) -> bool {
            units < DEFAULT_THRESHOLD
        }
        self.levels
            .iter()
            .filter(|(_, units)| below_threshold(**units))
            .map(|(sku, units)| (sku.clone(), self.restock_quantity(*units)))
            .collect()
    }
}

impl Restock for Inventory {
    fn restock_quantity(&self, current: u32) -> u32 {
        ((DEFAULT_THRESHOLD - current) as f64 * 1.5).ceil() as u32
    }
}

impl fmt::Display for Inventory {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} skus", self.levels.len())
    }
}

pub fn discounted_value(inventory: &Inventory, prices: &HashMap<String, f64>, pct: f64) -> f64 {
    inventory
        .levels
        .iter()
        .map(|(sku, units)| apply_discount(*prices.get(sku).unwrap_or(&0.0), pct) * *units as f64)
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reserve_reduces_stock() {
        let mut inventory = Inventory::new();
        inventory.levels.insert("a".into(), 3);
        assert!(inventory.reserve("a", 2).is_ok());
    }
}
