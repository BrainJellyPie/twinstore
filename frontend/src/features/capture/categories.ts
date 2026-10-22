// Catalog categories the capture pipeline maps products to (backend engine/layout_gen/catalog.py),
// with a color per category for the photo overlay. Keys are the backend's values; labels are message keys.

import type { MessageKey } from "@/shared/i18n/messages";

export const CAPTURE_CATEGORIES: { key: string; label: MessageKey; color: string }[] = [
  { key: "soft_drinks", label: "capCatSoftDrinks", color: "#2f80ed" },
  { key: "water_sports", label: "capCatWaterSports", color: "#22b8cf" },
  { key: "energy_coffee", label: "capCatEnergyCoffee", color: "#7048e8" },
  { key: "dairy", label: "capCatDairy", color: "#74c0fc" },
  { key: "beer_alcohol", label: "capCatBeerAlcohol", color: "#f59f00" },
  { key: "chips", label: "capCatChips", color: "#e8590c" },
  { key: "sweets", label: "capCatSweets", color: "#e64980" },
  { key: "instant_food", label: "capCatInstantFood", color: "#d9480f" },
  { key: "fresh_meals", label: "capCatFreshMeals", color: "#2b8a3e" },
  { key: "bakery", label: "capCatBakery", color: "#b08968" },
  { key: "ice_cream", label: "capCatIceCream", color: "#4dabf7" },
  { key: "household", label: "capCatHousehold", color: "#868e96" },
  { key: "health_beauty", label: "capCatHealthBeauty", color: "#cc5de8" },
  { key: "stationery", label: "capCatStationery", color: "#5c7cfa" },
  { key: "car_care", label: "capCatCarCare", color: "#495057" },
  { key: "fresh_produce", label: "capCatFreshProduce", color: "#40c057" },
  { key: "souvenirs", label: "capCatSouvenirs", color: "#f783ac" },
  { key: "checkout_impulse", label: "capCatCheckoutImpulse", color: "#fab005" },
  { key: "coffee_station", label: "capCatCoffeeStation", color: "#845ef7" },
];

const BY_KEY = new Map(CAPTURE_CATEGORIES.map((c) => [c.key, c]));

export function categoryLabel(key: string, t: (key: MessageKey) => string): string {
  const known = BY_KEY.get(key);
  return known ? t(known.label) : key ? key.replace(/_/g, " ") : t("capCatUnknown");
}

export function categoryColor(key: string): string {
  return BY_KEY.get(key)?.color ?? "#adb5bd";
}
