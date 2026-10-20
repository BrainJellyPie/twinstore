import { ChevronRight, Settings } from "lucide-react";
import { Link, useLocation } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/queries/keys";
import * as api from "@/shared/api/client";

export function AppHeader() {
  const location = useLocation();
  const isHome = location.pathname === "/";
  const isProject = location.pathname.startsWith("/projects/") && location.pathname !== "/projects/new";
  const match = location.pathname.match(/^\/projects\/([^/]+)/);
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
          {isProject && projectName && (
            <>
              <ChevronRight className="size-3" />
              <span className="text-foreground">{projectName}</span>
            </>
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
