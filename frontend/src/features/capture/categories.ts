// Catalog categories the capture pipeline maps products to (backend engine/layout_gen/catalog.py),
// with a color per category for the photo overlay.

export const CAPTURE_CATEGORIES: { key: string; label: string; color: string }[] = [
  { key: "soft_drinks", label: "Drinks", color: "#2f80ed" },
  { key: "water_sports", label: "Water & sports drinks", color: "#22b8cf" },
  { key: "energy_coffee", label: "Energy & coffee drinks", color: "#7048e8" },
  { key: "dairy", label: "Dairy drinks", color: "#74c0fc" },
  { key: "beer_alcohol", label: "Beer & alcohol", color: "#f59f00" },
  { key: "chips", label: "Snacks", color: "#e8590c" },
  { key: "sweets", label: "Candy & cookies", color: "#e64980" },
  { key: "instant_food", label: "Instant noodles & food", color: "#d9480f" },
  { key: "fresh_meals", label: "Fresh meals", color: "#2b8a3e" },
  { key: "bakery", label: "Bakery", color: "#b08968" },
  { key: "ice_cream", label: "Ice cream & frozen", color: "#4dabf7" },
  { key: "household", label: "Household", color: "#868e96" },
  { key: "health_beauty", label: "Health & beauty", color: "#cc5de8" },
  { key: "stationery", label: "Stationery", color: "#5c7cfa" },
  { key: "car_care", label: "Car care", color: "#495057" },
  { key: "fresh_produce", label: "Fresh produce", color: "#40c057" },
  { key: "souvenirs", label: "Gifts & travel", color: "#f783ac" },
  { key: "checkout_impulse", label: "Checkout treats", color: "#fab005" },
  { key: "coffee_station", label: "Coffee station", color: "#845ef7" },
];

const BY_KEY = new Map(CAPTURE_CATEGORIES.map((c) => [c.key, c]));

export function categoryLabel(key: string): string {
  return BY_KEY.get(key)?.label ?? (key ? key.replace(/_/g, " ") : "Unknown");
}

export function categoryColor(key: string): string {
  return BY_KEY.get(key)?.color ?? "#adb5bd";
}
