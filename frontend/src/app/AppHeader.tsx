// Top bar: where you are, with the store's name set in the display face.

import { Link, useLocation } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";

import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";

const PAGE_TITLES: Record<string, string> = {
  "/": "Home",
  "/projects/new": "New store",
  "/settings": "Settings",
};

export function AppHeader() {
  const location = useLocation();
  const isTown = location.pathname.startsWith("/town/");
  const isCapture = location.pathname.startsWith("/capture/");
  const sub = isTown ? "Neighborhood" : isCapture ? "Shelf capture" : null;
  const pid = location.pathname.match(/^\/(?:projects|town|capture)\/([^/]+)/)?.[1];
  const inProject = !!pid && pid !== "new";

  const { data: project } = useQuery({
    queryKey: inProject ? queryKeys.project(pid!) : ["project", "disabled"],
    queryFn: ({ signal }) => api.getProject(pid!, signal),
    enabled: inProject,
  });
  const projectName = project?.metadata.name;
  const title = PAGE_TITLES[location.pathname];

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-surface/80 px-5 backdrop-blur">
      {inProject ? (
        <nav className="flex min-w-0 items-center gap-2" aria-label="Breadcrumb">
          <Link to="/" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Stores
          </Link>
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          {sub ? (
            <Link to="/projects/$pid" params={{ pid: pid! }} className="truncate font-display text-lg font-semibold hover:underline">
              {projectName ?? "…"}
            </Link>
          ) : (
            <span className="truncate font-display text-lg font-semibold">{projectName ?? "…"}</span>
          )}
          {sub && (
            <>
              <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              <span className="font-display text-lg font-semibold">{sub}</span>
            </>
          )}
        </nav>
      ) : (
        <h1 className="font-display text-lg font-semibold">{title ?? "Parastore"}</h1>
      )}
    </header>
  );
}
