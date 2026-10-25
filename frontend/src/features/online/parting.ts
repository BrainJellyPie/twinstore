import type { SessionStep } from "@/shared/api/online";

/** The first step at which two visits differ (page, address, pick or search), or null when they never do. */
export function partingStep(a: SessionStep[], b: SessionStep[]): number | null {
  const same = (x: SessionStep, y: SessionStep) =>
    x.page === y.page && x.url === y.url && x.search_text === y.search_text
    && (x.choice?.kind ?? "") === (y.choice?.kind ?? "") && (x.choice?.label ?? "") === (y.choice?.label ?? "");
  for (let i = 0; i < Math.min(a.length, b.length); i++) if (!same(a[i]!, b[i]!)) return i;
  return a.length === b.length ? null : Math.min(a.length, b.length);
}
