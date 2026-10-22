// The run dialog's shared-store choice and the run option it becomes.

import type { OperationsConfig } from "@/shared/api/client";

/** The form's text, kept as typed so a half-written number is not rewritten under the cursor. */
export interface SharedStoreChoice {
  enabled: boolean;
  stock: string;      // units per shelf level
  restock: string;    // minutes; "" = only overnight
  tills: string;      // tills open; "" = every till
  patience: string;   // minutes
}

export const DEFAULT_SHARED_STORE: SharedStoreChoice = { enabled: true, stock: "12", restock: "120", tills: "", patience: "5" };

export function wholeIn(text: string, min: number, max: number): number | null {
  const value = Number(text.trim());
  return text.trim() !== "" && Number.isInteger(value) && value >= min && value <= max ? value : null;
}

/** The run option for the choice: undefined when shoppers each have the store alone, "invalid" for a value out of
 *  range. Blank refill and tills mean "only overnight" and "every till". */
export function sharedStoreOptions(choice: SharedStoreChoice): OperationsConfig | undefined | "invalid" {
  if (!choice.enabled) return undefined;
  const stock = wholeIn(choice.stock, 1, 10_000);
  const restock = choice.restock.trim() === "" ? null : wholeIn(choice.restock, 5, 1440);
  const tills = choice.tills.trim() === "" ? null : wholeIn(choice.tills, 1, 50);
  const patience = Number(choice.patience.trim());
  const patienceOk = choice.patience.trim() !== "" && Number.isFinite(patience) && patience >= 0.5 && patience <= 120;
  if (stock === null || (choice.restock.trim() !== "" && restock === null)
      || (choice.tills.trim() !== "" && tills === null) || !patienceOk) {
    return "invalid";
  }
  return {
    stock_per_facing: stock,
    restock_every_min: restock,
    open_counters: tills,
    patience_sec: Math.round(patience * 60),
  };
}
