import { expect, it } from "vitest";
import { figureSection } from "../figureSections";

it("finds the report section of each kind of fact-sheet line", () => {
  const lines: [string, string | null][] = [
    ["Quick add minus control (same shoppers, 95 % interval): conversion +2.0 pt [-1.0 pt, +5.0 pt] (not clear: interval includes zero).", "online-compare"],
    ["Quick add vs control: orders won 3, lost 1, visits that ended differently 6.", "online-changed"],
    ["Threadline overall conversion: 33.3% (10 orders / 30 visits).", "online-kpis"],
    ["Threadline revenue: $288.42, revenue per visit $9.61, average order $28.84.", "online-kpis"],
    ["Threadline funnel: visit 30 (100%); product_view 27 (90%).", "online-funnel"],
    ["Threadline pages where shoppers left without buying: category 8; home 4.", "online-funnel"],
    ["Threadline cart reminder: emails 16, came back 2, recovered orders 1, recovered revenue $12.18, discount given $0.80.", "online-recovery"],
    ["Threadline lost to the rival shop: left without buying 12, tried the rival 5, bought there 2, rival revenue $40.00.", "online-rival"],
    ["Glow Room ad Gentle Daily Shampoo (hero_banner): impressions 70, clicks 3 (4.3%), orders after a click 0, cost $1.50.", "online-ads"],
    ["Threadline friction: popup_shown in 30 visits (100%).", "online-frictions"],
    ["Threadline exit survey (12 answers): satisfaction 5.1/7, ease 5.4/7, NPS +8, would return 60%.", "online-surveys"],
    ["Threadline conversion by device: desktop: visits 14, conversion 14.3%; mobile: visits 16, conversion 50.0%.", "online-segments"],
    ["Threadline searches (count / found nothing / ordered): 'eyewear' 3/0/2.", "online-products"],
    ["Run: Threadline vs Quick add. Shoppers: 30 (rule shoppers).", null],
  ];
  for (const [line, section] of lines) expect([line, figureSection(line)]).toEqual([line, section]);
});
