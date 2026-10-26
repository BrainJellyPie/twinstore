/** Scrolling glides unless the system asks for less motion, which a script's "smooth" would otherwise ignore. */
export const smoothScroll = (): ScrollBehavior =>
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
