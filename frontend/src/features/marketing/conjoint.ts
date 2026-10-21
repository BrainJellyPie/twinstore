// Market simulator over a conjoint study: logit shares of preference for products made of the tested levels, at any
// price inside the tested range. Uses the point estimates of the pooled model.

import type { ConjointReport } from "@/shared/api/marketing";

export interface SimProduct {
  /** Level index per attribute, in the order of `report.attributes`. */
  levels: number[];
  /** Minor units; ignored when the study has no price attribute. */
  price: number;
}

export function utility(r: ConjointReport, p: SimProduct): number {
  let u = 0;
  r.attributes.forEach((a, i) => {
    u += r.part_worths.find((w) => w.attribute === a.name && w.level === a.levels[p.levels[i] ?? 0])?.utility ?? 0;
  });
  if (r.prices.length && r.price_slope != null) u += r.price_slope * (p.price - r.price_mean);
  return u;
}

/** Shares of preference for each product, plus "none" (last) when the study offered it. */
export function shares(r: ConjointReport, products: SimProduct[], withNone = r.none_option): number[] {
  const us = products.map((p) => utility(r, p));
  if (withNone && r.none_utility != null) us.push(r.none_utility);
  const top = Math.max(...us);
  const e = us.map((u) => Math.exp(u - top));
  const sum = e.reduce((a, b) => a + b, 0);
  return e.map((x) => x / sum);
}

/** The first product's share as its price moves across the tested range, the other products held fixed. */
export function shareCurve(r: ConjointReport, products: SimProduct[], steps = 24): { price: number; share: number }[] {
  if (!r.prices.length || !products.length) return [];
  const lo = Math.min(...r.prices);
  const hi = Math.max(...r.prices);
  return Array.from({ length: steps + 1 }, (_, i) => {
    const price = Math.round(lo + ((hi - lo) * i) / steps);
    return { price, share: shares(r, [{ ...products[0]!, price }, ...products.slice(1)])[0]! };
  });
}

/** A starting line-up: the best level of every attribute at the middle price, against the first levels at the lowest. */
export function defaultLineup(r: ConjointReport): SimProduct[] {
  const best = r.attributes.map((a) => {
    const pw = a.levels.map((l) => r.part_worths.find((w) => w.attribute === a.name && w.level === l)?.utility ?? 0);
    return pw.indexOf(Math.max(...pw));
  });
  const sorted = [...r.prices].sort((a, b) => a - b);
  const mid = sorted[Math.floor(sorted.length / 2)] ?? 0;
  const base = r.attributes.map(() => 0);
  return [{ levels: best, price: mid }, { levels: base, price: sorted[0] ?? 0 }];
}
