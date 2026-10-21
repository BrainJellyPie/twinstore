// The store a route belongs to: /projects/:pid, /town/:pid, /capture/:pid and /marketing/:pid (not /projects/new).
export function projectIdFromPath(pathname: string): string | null {
  const pid = pathname.match(/^\/(?:projects|town|capture|marketing)\/([^/]+)/)?.[1];
  return pid && pid !== "new" ? pid : null;
}
