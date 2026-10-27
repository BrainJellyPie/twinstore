import type { KeyboardEvent } from "react";

function step<T extends string>(event: KeyboardEvent<HTMLElement>, ids: readonly T[], current: T, select: (id: T) => void,
  role: "tab" | "radio") {
  const at = ids.indexOf(current);
  const forward = event.key === "ArrowRight" || (role === "radio" && event.key === "ArrowDown");
  const back = event.key === "ArrowLeft" || (role === "radio" && event.key === "ArrowUp");
  const next = forward ? ids[(at + 1) % ids.length]
    : back ? ids[(at - 1 + ids.length) % ids.length]
      : event.key === "Home" ? ids[0] : event.key === "End" ? ids[ids.length - 1] : undefined;
  if (next === undefined) return;
  event.preventDefault();
  select(next);
  event.currentTarget.querySelectorAll<HTMLElement>(`[role="${role}"]`)[ids.indexOf(next)]?.focus();
}

/** ←/→, Home and End on a row of tabs (WAI-ARIA tabs): select the neighbouring tab and move focus to it. Only the
 *  selected tab is in the Tab order (tabIndex 0, the others -1), so the keys are how the others are reached. */
export function onTabKeys<T extends string>(event: KeyboardEvent<HTMLElement>, ids: readonly T[], current: T, select: (id: T) => void) {
  step(event, ids, current, select, "tab");
}

/** The same for a radio group of buttons (WAI-ARIA radio group), where ↑/↓ move too. Only the checked option is in
 *  the Tab order. */
export function onRadioKeys<T extends string>(event: KeyboardEvent<HTMLElement>, ids: readonly T[], current: T, select: (id: T) => void) {
  step(event, ids, current, select, "radio");
}
