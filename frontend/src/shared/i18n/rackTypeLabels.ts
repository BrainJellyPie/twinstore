// A rack's type as it reads in the selected language, lowercase for use inside a sentence or label ("fridge Drink 1
// at 2,0"). The type values themselves are backend contract values and are not changed.

import type { MessageKey } from "./messages";

type Translate = (key: MessageKey, values?: Record<string, string | number>) => string;

const LABELS: Record<string, MessageKey> = {
  shelf: "gridType_shelf", fridge: "gridType_fridge", counter: "gridType_counter", table: "gridType_table",
  entrance: "gridType_entrance", exit: "gridType_exit",
};

/** Unknown types are shown as they are. */
export function rackTypeLabel(type: string, t: Translate): string {
  return Object.prototype.hasOwnProperty.call(LABELS, type) ? t(LABELS[type]!) : type;
}
