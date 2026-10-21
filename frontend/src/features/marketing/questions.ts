import type { QuestionKind } from "@/shared/api/marketing";

export const QUESTIONS: { kind: QuestionKind; label: string; hint: string; multi?: boolean }[] = [
  { kind: "purchase_intent", label: "Purchase intent", hint: "How likely to buy on the next trip (1–5)" },
  { kind: "appeal", label: "Pack appeal", hint: "How appealing the package looks (1–5)" },
  { kind: "value", label: "Value for money", hint: "How good value it seems (1–5)" },
  { kind: "uniqueness", label: "Stand-out", hint: "How different from the usual shelf (1–5)" },
  { kind: "price_vw", label: "Price range", hint: "Van Westendorp: too cheap, bargain, expensive, too expensive (product A)" },
  { kind: "preference", label: "Preference", hint: "Which one they would take home", multi: true },
  { kind: "open", label: "Why", hint: "One open answer per respondent" },
];
