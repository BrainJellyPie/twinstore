// After an update, a tab still running the previous version asks for script chunks the new build no longer has
// (their names carry a content hash). The page is reloaded once to load the new version instead of showing an error.

const KEY = "twinstore.reloadedForUpdate";
const STALE = /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed|Unable to preload CSS/i;

export function isStaleBuildError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : "";
  return STALE.test(message);
}

/** Reloads the page unless it already did so in the last minute (then the failure is real and is shown). Returns
 *  whether it reloads. Without session storage it does not, rather than risk reloading for ever. */
export function reloadForNewVersion(reload: () => void = () => window.location.reload(), now = Date.now()): boolean {
  try {
    const last = Number(sessionStorage.getItem(KEY) ?? 0);
    if (now - last < 60_000) return false;
    sessionStorage.setItem(KEY, String(now));
  } catch {
    return false;
  }
  reload();
  return true;
}
