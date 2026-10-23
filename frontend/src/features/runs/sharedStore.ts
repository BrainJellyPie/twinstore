// The run dialog's shared-store choice and the run option it becomes.

import type { OperationsConfig } from "@/shared/api/client";

/** The form's text, kept as typed so a half-written number is not rewritten under the cursor. */
export interface SharedStoreChoice {
  enabled: boolean;
  stock: string;      // units per shelf level
  restock: string;    // minutes; "" = only overnight
  tills: string;      // tills open; "" = every till
  patience: string;   // minutes
  crowd: string;      // shoppers at one shelf that feel crowded; "" = crowding has no effect
  backroom: string;   // units per product behind the shelves; "" = endless
  delivery: boolean;  // a delivery tops the backroom up each morning
  crew: string;       // staff who serve at the tills and refill shelves; "" = tills staffed on their own
  refillAt: string;   // with a crew: refill a shelf once down to this % of full
}

export const DEFAULT_SHARED_STORE: SharedStoreChoice = {
  enabled: true, stock: "12", restock: "120", tills: "", patience: "5", crowd: "4", backroom: "", delivery: true,
  crew: "", refillAt: "50",
};

export function wholeIn(text: string, min: number, max: number): number | null {
  const value = Number(text.trim());
  return text.trim() !== "" && Number.isInteger(value) && value >= min && value <= max ? value : null;
}

export function numberIn(text: string, min: number, max: number): number | null {
  const value = Number(text.trim());
  return text.trim() !== "" && Number.isFinite(value) && value >= min && value <= max ? value : null;
}

/** The run option for the choice: undefined when shoppers each have the store alone, "invalid" for a value out of
 *  range. Blank refill and tills mean "only overnight" and "every till". */
export function sharedStoreOptions(choice: SharedStoreChoice): OperationsConfig | undefined | "invalid" {
  if (!choice.enabled) return undefined;
  const stock = wholeIn(choice.stock, 1, 10_000);
  const restock = choice.restock.trim() === "" ? null : wholeIn(choice.restock, 5, 1440);
  const tills = choice.tills.trim() === "" ? null : wholeIn(choice.tills, 1, 50);
  const patience = numberIn(choice.patience, 10 / 60, 120);
  const crowd = choice.crowd.trim() === "" ? null : wholeIn(choice.crowd, 2, 50);
  const backroom = choice.backroom.trim() === "" ? null : wholeIn(choice.backroom, 0, 1_000_000);
  const crew = choice.crew.trim() === "" ? null : wholeIn(choice.crew, 1, 100);
  const refillAt = numberIn(choice.refillAt, 0, 95);
  if (stock === null || (choice.restock.trim() !== "" && restock === null)
      || (choice.tills.trim() !== "" && tills === null) || patience === null || (choice.crowd.trim() !== "" && crowd === null)
      || (choice.backroom.trim() !== "" && backroom === null) || (choice.crew.trim() !== "" && crew === null)
      || (crew !== null && refillAt === null)) {
    return "invalid";
  }
  return {
    stock_per_facing: stock,
    restock_every_min: restock,
    open_counters: tills,
    patience_sec: patience * 60,
    crowd_limit: crowd,
    backroom_per_product: backroom,
    daily_delivery: choice.delivery,
    crew,
    ...(crew !== null && refillAt !== null ? { refill_at: refillAt / 100 } : {}),
  };
}

/** The form for a run's own settings (the operations lab starts from them). */
export function choiceFromConfig(config: OperationsConfig): SharedStoreChoice {
  return {
    enabled: true,
    stock: String(config.stock_per_facing ?? 12),
    restock: config.restock_every_min == null ? "" : String(config.restock_every_min),
    tills: config.open_counters == null ? "" : String(config.open_counters),
    patience: String((config.patience_sec ?? 300) / 60),
    // Reports from before crowding have no setting: crowding had no effect then.
    crowd: config.crowd_limit == null ? "" : String(config.crowd_limit),
    backroom: config.backroom_per_product == null ? "" : String(config.backroom_per_product),
    delivery: config.daily_delivery ?? true,
    crew: config.crew == null ? "" : String(config.crew),
    refillAt: String((config.refill_at ?? 0.5) * 100),
  };
}
