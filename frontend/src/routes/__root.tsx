import { useQuery } from "@tanstack/react-query";
import { createRootRoute, Outlet, useLocation } from "@tanstack/react-router";
import { Suspense, useEffect, useRef } from "react";
import { AppBackdrop } from "@/app/AppBackdrop";
import { CommandBar } from "@/app/CommandBar";
import { CommandPalette } from "@/app/CommandPalette";
import { ModelSetupBanner } from "@/app/ModelSetupBanner";
import { RunNotice } from "@/app/RunNotice";
import { ShortcutsSheet } from "@/app/ShortcutsSheet";
import { projectIdFromPath } from "@/app/paths";
import { TabCloseNotice } from "@/app/QuitTwinStore";
import { StoreMissing } from "@/app/RouteError";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { useI18n } from "@/shared/i18n/i18n";
import { queryKeys } from "@/shared/queries/keys";
import { LoadingView } from "@/shared/components/LoadingView";
import { RouteErrorBoundary } from "@/app/providers/RouteErrorBoundary";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  const { t } = useI18n();
  const { pathname, href } = useLocation();
  const main = useRef<HTMLElement>(null);
  // Going to another page removes what had focus (a palette entry, a link): keyboard users carry on from the new
  // page's content instead of the top of the document. The old page or a closing palette can keep focus a moment
  // longer, so watch until focus leaves it; anything else taking focus meanwhile is left alone.
  const shown = useRef(href);
  useEffect(() => {
    if (shown.current === href) return;
    shown.current = href;
    const stale = document.activeElement;
    let tries = 0;
    const timer = window.setInterval(() => {
      const now = document.activeElement;
      if (now === document.body) main.current?.focus({ preventScroll: true });
      if ((now !== document.body && now !== stale) || ++tries >= 20) window.clearInterval(timer);
    }, 100);
    return () => window.clearInterval(timer);
  }, [href]);
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
      <a href="#main" onClick={(event) => { event.preventDefault(); main.current?.focus(); }}
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[100] focus:rounded-xl focus:bg-card focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:shadow-lg">
        {t("skipToContent")}
      </a>
      <CommandBar />
      <TabCloseNotice />
      <ModelSetupBanner />
      <main ref={main} id="main" tabIndex={-1} className="relative z-10 flex min-h-0 flex-1 overflow-hidden outline-none">
        <RouteErrorBoundary>
          {missing ? <StoreMissing detail={project.error?.message} /> : (
            <Suspense fallback={<LoadingView />}>
              <Outlet />
            </Suspense>
          )}
        </RouteErrorBoundary>
      </main>
      <CommandPalette />
      <RunNotice />
      <ShortcutsSheet />
    </div>
  );
}
