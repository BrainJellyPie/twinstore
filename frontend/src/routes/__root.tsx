import { useQuery } from "@tanstack/react-query";
import { createRootRoute, Outlet, useLocation } from "@tanstack/react-router";
import { Suspense } from "react";
import { AppBackdrop } from "@/app/AppBackdrop";
import { CommandBar } from "@/app/CommandBar";
import { CommandPalette } from "@/app/CommandPalette";
import { ModelSetupBanner } from "@/app/ModelSetupBanner";
import { projectIdFromPath } from "@/app/paths";
import { TabCloseNotice } from "@/app/QuitTwinStore";
import { StoreMissing } from "@/app/RouteError";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { queryKeys } from "@/shared/queries/keys";
import { LoadingView } from "@/shared/components/LoadingView";
import { RouteErrorBoundary } from "@/app/providers/RouteErrorBoundary";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  const { pathname } = useLocation();
  const pid = projectIdFromPath(pathname);
  // The 3D floor fills the screen: freeze the ambient light behind it.
  const calm = pathname.startsWith("/projects/") && !!pid;
  // A store page of a deleted store (an old link or bookmark) says so instead of showing an empty page.
  const project = useQuery({
    queryKey: pid ? queryKeys.project(pid) : ["project", "disabled"],
    queryFn: ({ signal }) => api.getProject(pid!, signal),
    enabled: !!pid,
  });
  const missing = !!pid && project.error instanceof ApiError && project.error.status === 404;
  return (
    <div className="relative flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <AppBackdrop calm={calm} />
      <CommandBar />
      <TabCloseNotice />
      <ModelSetupBanner />
      <main className="relative z-10 flex min-h-0 flex-1 overflow-hidden">
        <RouteErrorBoundary>
          {missing ? <StoreMissing detail={project.error?.message} /> : (
            <Suspense fallback={<LoadingView />}>
              <Outlet />
            </Suspense>
          )}
        </RouteErrorBoundary>
      </main>
      <CommandPalette />
    </div>
  );
}
