import type { KeyboardEvent } from "react";

/** ←/→, Home and End on a row of tabs (WAI-ARIA tabs): select the neighbouring tab and move focus to it. Only the
 *  selected tab is in the Tab order (tabIndex 0, the others -1), so the keys are how the others are reached. */
export function onTabKeys<T extends string>(event: KeyboardEvent<HTMLElement>, ids: readonly T[], current: T, select: (id: T) => void) {
  const at = ids.indexOf(current);
  const next = event.key === "ArrowRight" ? ids[(at + 1) % ids.length]
    : event.key === "ArrowLeft" ? ids[(at - 1 + ids.length) % ids.length]
      : event.key === "Home" ? ids[0] : event.key === "End" ? ids[ids.length - 1] : undefined;
  if (next === undefined) return;
  event.preventDefault();
  select(next);
  event.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]')[ids.indexOf(next)]?.focus();
}
