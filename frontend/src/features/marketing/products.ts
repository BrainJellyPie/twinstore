// Products and fixtures of a layout, flattened for the marketing builders.

import type { Store } from "@/shared/types/domain";

export interface Product {
  sku: string;
  name: string;
  price: number;
  regularPrice: number;
  promo: string;
  facings: number;
  racks: string[];
}

export interface Fixture { id: string; name: string; levels: number; category: string }

export function storeProducts(store: Store | null | undefined): Product[] {
  const out = new Map<string, Product>();
  for (const rack of store?.racks ?? []) {
    for (const slot of rack.slots) {
      for (const item of slot.items) {
        const p = out.get(item.sku) ?? {
          sku: item.sku, name: item.name, price: item.price, regularPrice: item.regular_price ?? 0, promo: item.promo, facings: 0, racks: [],
        };
        p.facings += 1;
        const where = rack.rack_name || rack.id;
        if (!p.racks.includes(where)) p.racks.push(where);
        out.set(item.sku, p);
      }
    }
  }
  return [...out.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export function storeFixtures(store: Store | null | undefined): Fixture[] {
  return (store?.racks ?? [])
    .filter((r) => r.slots.length > 0 || r.type === "shelf" || r.type === "fridge")
    .map((r) => ({ id: r.id, name: r.rack_name || r.id, levels: Math.min(4, r.levels || 4), category: r.rack_name.replace(/\s*\d+$/, "") }));
}

/** Category names a price change can address: rack names without their running number ("Drink 1" → "Drink"). */
export function storeCategories(store: Store | null | undefined): string[] {
  return [...new Set(storeFixtures(store).filter((f) => f.category).map((f) => f.category))].sort();
}

export function toMinor(text: string, divisor: number): number | null {
  const amount = text.trim().replace(/^[$€£¥₩]\s*|\s*[$€£¥₩]$/g, "");
  if (!/^(?:(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d*)?|\.\d+)$/.test(amount)) return null;
  const minor = Math.round(Number(amount.replace(/,/g, "")) * divisor);
  return Number.isSafeInteger(minor) && minor >= 0 ? minor : null;
}
