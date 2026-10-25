// An online analyst's answer often names a cause a quick experiment can test (a popup, fees, forced sign-in, empty
// searches, slow pages…). These cues read the answer and the report lines it cites (written in English) and pick the
// experiments that would test it, in the order the answer brings them up.

const CUES: [RegExp, string[]][] = [
  [/pop-?up/i, ["no_popup"]],
  [/service fee|last-step fee|\bfee_(?:seen|left)\b/i, ["no_service_fee"]],
  [/deliver|shipping/i, ["free_delivery", "lower_threshold"]],
  [/\bsign[- ]?in(?:_|\b)|\blog[- ]?in\b|create an account|account_created/i, ["guest_checkout"]],
  [/found nothing|zero_results|no results|empty search/i, ["smart_search"]],
  [/slow|loading|load time|timed_out|ran out of patience/i, ["faster"]],
  [/cookie/i, ["no_cookie_banner"]],
  [/add-?on/i, ["untick_addon"]],
  [/checkout steps|multi-?step|long checkout/i, ["one_page"]],
  [/abandon/i, ["cart_reminder", "reminder_discount"]],
  [/sponsored/i, ["no_sponsored"]],
  [/urgency|pressure|only \d+ left/i, ["no_pressure"]],
  [/pay later|wallet|apple pay|payment method/i, ["wallets"]],
  [/expensive|too high|price/i, ["prices_down", "best_seller_deals"]],
  [/small text|eyesight|low vision/i, ["large_text"]],
];

/** Up to three experiments, of those that apply to the store, that would test what the answer points at. */
export function experimentsForAnswer(text: string, figures: string[], applicable: Set<string>): string[] {
  const said = [text, ...figures].join("\n");
  const found = CUES
    .map(([cue, ids]) => ({ at: said.search(cue), ids }))
    .filter((c) => c.at >= 0)
    .sort((a, b) => a.at - b.at)
    .flatMap((c) => c.ids)
    .filter((id) => applicable.has(id));
  return [...new Set(found)].slice(0, 3);
}
