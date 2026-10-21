const COMMON = new Set(["the", "and", "for", "with", "our", "this", "that", "staff", "script", "pitch", "more", "less", "new"]);

/** The product a sentence names: its full name when present, else the one sharing the most words (3+ letters). */
export function productNamedIn(text: string, products: readonly { sku: string; name: string }[]): string | null {
  const lower = text.toLowerCase();
  const whole = products.filter((p) => p.name.trim() && lower.includes(p.name.trim().toLowerCase()))
    .sort((x, y) => y.name.length - x.name.length)[0];
  if (whole) return whole.sku;
  const words = new Set(lower.split(/[^\p{L}\p{N}]+/u).filter((w) => Array.from(w).length >= 3 && !COMMON.has(w)));
  let best: { sku: string; hits: number } | null = null;
  for (const p of products) {
    const hits = new Set(p.name.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((w) => words.has(w))).size;
    if (hits > 0 && (!best || hits > best.hits)) best = { sku: p.sku, hits };
  }
  return best?.sku ?? null;
}
