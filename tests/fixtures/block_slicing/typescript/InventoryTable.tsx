import React, { useMemo, useState } from "react";
import { Inventory } from "./inventory";
import { formatUnits } from "../util/format";

type Props = {
  inventory: Inventory;
  skus: string[];
};

const HEADER = ["SKU", "Units", "Status"];

function statusLabel(units: number): string {
  if (units === 0) {
    return "out of stock";
  }
  return units < 5 ? "low" : "ok";
}

// Größe 🚀: multibyte characters before a component.
export function InventoryTable({ inventory, skus }: Props) {
  const [filter, setFilter] = useState("");
  const rows = useMemo(
    () => skus.filter((sku) => sku.includes(filter)).map((sku) => ({ sku, units: inventory.totalUnits })),
    [skus, filter, inventory],
  );

  const handleReserve = (sku: string) => {
    inventory.reserve(sku, 1);
    setFilter(filter);
  };

  return (
    <table>
      <thead>
        <tr>{HEADER.map((h) => <th key={h}>{h}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.sku} onClick={() => handleReserve(row.sku)}>
            <td>{row.sku}</td>
            <td>{formatUnits(row.units)}</td>
            <td>{statusLabel(row.units)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function EmptyInventory() {
  return <p>No inventory yet.</p>;
}
