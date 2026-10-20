import { ChevronRight, Map, Settings } from "lucide-react";
import { Link, useLocation } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/queries/keys";
import * as api from "@/shared/api/client";

export function AppHeader() {
  const location = useLocation();
  const isHome = location.pathname === "/";
  const isProject = location.pathname.startsWith("/projects/") && location.pathname !== "/projects/new";
  const isTown = location.pathname.startsWith("/town/");
  const match = location.pathname.match(/^\/(?:projects|town)\/([^/]+)/);
  const pid = match?.[1];

  const { data: project } = useQuery({
    queryKey: pid ? queryKeys.project(pid) : ["project", "disabled"],
    queryFn: ({ signal }) => api.getProject(pid!, signal),
    enabled: !!pid && pid !== "new",
  });

  const projectName = project?.metadata.name;

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b bg-background px-4">
      <Link to="/" className="flex items-center gap-2">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <span className="text-sm font-bold">P</span>
        </div>
        <span className="text-sm font-semibold tracking-tight">Parastore</span>
      </Link>

      {!isHome && (
        <nav className="flex items-center gap-1 text-xs text-muted-foreground">
          <Link to="/" className="hover:text-foreground transition-colors">Home</Link>
          {(isProject || isTown) && projectName && (
            <>
              <ChevronRight className="size-3" />
              <Link to="/projects/$pid" params={{ pid: pid! }} className="text-foreground hover:underline">{projectName}</Link>
            </>
          )}
          {isTown && (
            <>
              <ChevronRight className="size-3" />
              <span className="text-foreground">Neighborhood</span>
            </>
          )}
          {isProject && pid && (
            <Link
              to="/town/$pid"
              params={{ pid }}
              className="ml-3 flex items-center gap-1 rounded-md border px-2 py-0.5 text-foreground transition-colors hover:bg-muted"
            >
              <Map className="size-3" /> Neighborhood
            </Link>
          )}
        </nav>
      )}

      <Link
        to="/settings"
        className="ml-auto flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        aria-label="Settings"
      >
        <Settings className="size-4" /> Models
      </Link>
    </header>
  );
}
