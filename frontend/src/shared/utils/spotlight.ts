import type { MouseEvent } from "react";

// Pointer position as --mx / --my on the hovered element, for the `spotlight` utility's glow.
export function spotlightHandler(e: MouseEvent<HTMLElement>): void {
  const rect = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--mx", `${e.clientX - rect.left}px`);
  e.currentTarget.style.setProperty("--my", `${e.clientY - rect.top}px`);
}
