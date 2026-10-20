import { createRootRoute, Outlet } from "@tanstack/react-router";
import { Suspense } from "react";
import { AppHeader } from "@/app/AppHeader";
import { SideRail } from "@/app/SideRail";
import { LoadingView } from "@/shared/components/LoadingView";
import { RouteErrorBoundary } from "@/app/providers/RouteErrorBoundary";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  return (
    <div className="flex h-screen w-screen bg-background text-foreground">
      <SideRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader />
        <main className="flex min-h-0 flex-1 overflow-hidden">
          <RouteErrorBoundary>
            <Suspense fallback={<LoadingView />}>
              <Outlet />
            </Suspense>
          </RouteErrorBoundary>
        </main>
      </div>
    </div>
  );
}
