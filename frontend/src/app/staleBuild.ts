// After an update, a tab still running the previous version asks for script chunks the new build no longer has
// (their names carry a content hash). The page is reloaded once to load the new version instead of showing an error.
// The same error comes while the backend is stopped or restarting; then a reload would only show the browser's
// "can't be reached" page and lose the page's state, so the error is shown instead.

import { getHealth } from "@/shared/api/client";

const KEY = "twinstore.reloadedForUpdate";
const STALE = /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed|Unable to preload CSS/i;

export function isStaleBuildError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : "";
  return STALE.test(message);
}

/** "reloading", "offline" when the server does not answer, or "show" when the page reloaded in the last minute (the
 *  failure is real) or there is no session storage (rather than risk reloading for ever). */
export type StaleCheck = "reloading" | "offline" | "show";

export async function reloadForNewVersion(reload: () => void = () => window.location.reload(), now = Date.now(),
  serverAnswers: () => Promise<unknown> = () => getHealth()): Promise<StaleCheck> {
  try {
    if (now - Number(sessionStorage.getItem(KEY) ?? 0) < 60_000) return "show";
  } catch {
    return "show";
  }
  try {
    await serverAnswers();
  } catch {
    return "offline";
  }
  try {
    // Preload and route-error handlers can both await the same recovery.
    // Another check may have reloaded while this health request was pending.
    if (now - Number(sessionStorage.getItem(KEY) ?? 0) < 60_000) return "show";
    sessionStorage.setItem(KEY, String(now));
  } catch {
    return "show";
  }
  reload();
  return "reloading";
}
