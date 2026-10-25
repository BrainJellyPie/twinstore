// The store a route belongs to: /projects/:pid, /town/:pid, /capture/:pid, /marketing/:pid and /online/:pid (not
// /projects/new).
export function projectIdFromPath(pathname: string): string | null {
  const pid = pathname.match(/^\/(?:projects|town|capture|marketing|online)\/([^/]+)/)?.[1];
  return pid && pid !== "new" ? pid : null;
}

// localStorage key of the store opened last, which the nav tabs and the home page return to.
export const LAST_STORE = "twinstore.lastStore";

/** The store to offer off a store's pages: the one opened last if it still exists, else the only store. */
export function rememberedStore(projects: readonly { project_id: string }[] | undefined): string | null {
  let remembered: string | null = null;
  try { remembered = localStorage.getItem(LAST_STORE); } catch { /* storage unavailable: nothing remembered */ }
  if (projects?.some((p) => p.project_id === remembered)) return remembered;
  return projects?.length === 1 ? projects[0]!.project_id : null;
}
