import type { QuestionKind } from "@/shared/api/marketing";
import type { MessageKey } from "@/shared/i18n/messages";

export const QUESTIONS: { kind: QuestionKind; label: MessageKey; hint: MessageKey; multi?: boolean }[] = [
  { kind: "purchase_intent", label: "mkQPurchaseIntent", hint: "mkQPurchaseIntentHint" },
  { kind: "appeal", label: "mkQAppeal", hint: "mkQAppealHint" },
  { kind: "value", label: "mkQValue", hint: "mkQValueHint" },
  { kind: "uniqueness", label: "mkQUniqueness", hint: "mkQUniquenessHint" },
  { kind: "price_vw", label: "mkQPriceVw", hint: "mkQPriceVwHint" },
  { kind: "preference", label: "mkQPreference", hint: "mkQPreferenceHint", multi: true },
  { kind: "open", label: "mkQOpen", hint: "mkQOpenHint" },
];

/** The label of a question kind in the selected language; unknown kinds are shown as they are. */
export function questionLabel(kind: string, t: (key: MessageKey) => string): string {
  const q = QUESTIONS.find((x) => x.kind === kind);
  return q ? t(q.label) : kind;
}
