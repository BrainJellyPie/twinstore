import { createRootRoute, Outlet, useLocation } from "@tanstack/react-router";
import { Suspense } from "react";
import { AppBackdrop } from "@/app/AppBackdrop";
import { CommandBar } from "@/app/CommandBar";
import { CommandPalette } from "@/app/CommandPalette";
import { ModelSetupBanner } from "@/app/ModelSetupBanner";
import { projectIdFromPath } from "@/app/paths";
import { LoadingView } from "@/shared/components/LoadingView";
import { RouteErrorBoundary } from "@/app/providers/RouteErrorBoundary";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  const { pathname } = useLocation();
  // The 3D floor fills the screen: freeze the ambient light behind it.
  const calm = pathname.startsWith("/projects/") && !!projectIdFromPath(pathname);
  return (
    <div className="relative flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <AppBackdrop calm={calm} />
      <CommandBar />
      <ModelSetupBanner />
      <main className="relative z-10 flex min-h-0 flex-1 overflow-hidden">
        <RouteErrorBoundary>
          <Suspense fallback={<LoadingView />}>
            <Outlet />
          </Suspense>
        </RouteErrorBoundary>
      </main>
      <CommandPalette />
    </div>
  );
}
