import type { ProductEdit } from "@/shared/api/productEdits";
import { majorUnitText, minorUnitDivisor, toMinor } from "@/shared/utils/money";
export interface RowDraft { name?: string; price?: string; promo?: string }
export function priceText(minor: number, currency: string): string {
  return majorUnitText(minor, currency, { fixed: true });
}
export function draftEdits(drafts: Map<string, RowDraft>, currency: string): ProductEdit[] {
  if (drafts.size > 500) throw new Error("Edit at most 500 SKUs at a time.");
  return [...drafts].map(([sku, draft]) => {
    const edit: ProductEdit = { sku };
    if (draft.name !== undefined) {
      const name = draft.name.trim();
      if (!name || name.length > 200) throw new Error(`${sku}: Enter a name of 1–200 characters.`);
      edit.name = name;
    }
    if (draft.promo !== undefined) {
      if (draft.promo.trim().length > 200) throw new Error(`${sku}: Use at most 200 characters for the promotion.`);
      edit.promo = draft.promo.trim();
    }
    if (draft.price !== undefined) {
      const price = draft.price.length <= 100 ? toMinor(draft.price, minorUnitDivisor(currency)) : null;
      if (price === null) throw new Error(`${sku}: Enter a nonnegative price within the safe integer limit.`);
      edit.price = price;
    }
    return edit;
  });
}
