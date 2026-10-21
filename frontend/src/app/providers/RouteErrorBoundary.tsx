import type { ReactNode } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import { useQueryErrorResetBoundary } from "@tanstack/react-query";
import { useLocation, useNavigate, useRouterState } from "@tanstack/react-router";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";

function Fallback({ error, resetErrorBoundary }: FallbackProps) {
  const navigate = useNavigate();
  const pathname = useLocation({ select: location => location.pathname });
  const { t } = useI18n();
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto p-4">
      <div role="alert" className="my-auto w-full min-w-0 max-w-md shrink-0 self-center space-y-3 text-center">
        <div className="text-sm font-medium text-destructive">{t("routeErrorTitle")}</div>
        <div className="max-h-48 overflow-y-auto whitespace-pre-wrap text-xs text-muted-foreground [overflow-wrap:anywhere]">
          {error instanceof Error ? error.message : String(error)}
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (pathname === "/") resetErrorBoundary();
              else void navigate({ to: "/" });
            }}
          >
            {t("backToStores")}
          </Button>
          <Button variant="outline" size="sm" onClick={resetErrorBoundary}>
            {t("tryAgain")}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const { reset } = useQueryErrorResetBoundary();
  // Wait for the destination to commit so a pending navigation does not retry the old page.
  const resolvedHref = useRouterState({ select: state => state.resolvedLocation?.href ?? state.location.href });
  return (
    <ErrorBoundary FallbackComponent={Fallback} onReset={reset} resetKeys={[resolvedHref]}>
      {children}
    </ErrorBoundary>
  );
}
