// The store a route belongs to: /projects/:pid, /town/:pid, /capture/:pid, /marketing/:pid and /online/:pid (not
// /projects/new).
export function projectIdFromPath(pathname: string): string | null {
  const pid = pathname.match(/^\/(?:projects|town|capture|marketing|online)\/([^/]+)/)?.[1];
  return pid && pid !== "new" ? pid : null;
}
