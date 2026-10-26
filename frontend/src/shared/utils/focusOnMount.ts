/** Ref for what appears in place of, or below, the control pressed (a result, a confirmation): focus moves to it,
 * which also scrolls it into view, so keyboard and screen-reader users land on it. Module-level, so the ref is
 * stable and a re-render does not pull focus back. Give the element `tabIndex={-1}`. */
export const focusOnMount = (el: HTMLElement | null) => el?.focus();

/** The same for a result that opens below the control: it is scrolled to the top of the view, so it can be read. */
export const revealOnMount = (el: HTMLElement | null) => {
  el?.focus({ preventScroll: true });
  el?.scrollIntoView?.({ block: "start" });
};
