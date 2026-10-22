// A route that failed to load: after an update that is a script of the previous version, so the page reloads once;
// anything else shows the router's usual error.

import { ErrorComponent, type ErrorComponentProps } from "@tanstack/react-router";

import { isStaleBuildError, reloadForNewVersion } from "./staleBuild";

export function RouteError(props: ErrorComponentProps) {
  if (isStaleBuildError(props.error) && reloadForNewVersion()) return null;
  return <ErrorComponent error={props.error} />;
}
