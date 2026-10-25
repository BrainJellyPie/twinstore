// The analyst cites lines of the run's fact sheet; this finds the report section each kind of line is drawn in
// (wording from engine/online/analyst.py).

const FIGURE_SECTIONS: [RegExp, string][] = [
  [/ minus control /, "online-compare"],
  [/ vs control: | conversion difference by segment: /, "online-changed"],
  [/ overall conversion: | revenue: | engagement: /, "online-kpis"],
  [/ funnel: | visits ended: | pages where shoppers left /, "online-funnel"],
  [/ cart reminder: /, "online-recovery"],
  [/ lost to the rival shop: /, "online-rival"],
  [/ ad .+ impressions /, "online-ads"],
  [/ friction: /, "online-frictions"],
  [/ exit survey /, "online-surveys"],
  [/ conversion by /, "online-segments"],
  [/ top products | searches \(count/, "online-products"],
];

/** The report section a cited line comes from, if the report shows it. */
export function figureSection(line: string): string | null {
  return FIGURE_SECTIONS.find(([pattern]) => pattern.test(line))?.[1] ?? null;
}
