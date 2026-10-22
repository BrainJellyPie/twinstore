import type { ReactNode } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";

function Fallback({ error, resetErrorBoundary }: FallbackProps) {
  const { t } = useI18n();
  return (
    <div className="flex h-full w-full items-center justify-center bg-[#ece3d6]">
      <div className="max-w-sm rounded-lg bg-background/95 p-4 text-center shadow-md">
        <div className="text-sm font-medium text-destructive">{t("canvasError")}</div>
        <div className="mt-1 text-xs text-muted-foreground">
          {error instanceof Error ? error.message : String(error)}
        </div>
        <Button className="mt-3" variant="outline" size="sm" onClick={resetErrorBoundary}>
          {t("localRetry")}
        </Button>
      </div>
    </div>
  );
}

export function CanvasErrorBoundary({ children }: { children: ReactNode }) {
  return <ErrorBoundary FallbackComponent={Fallback}>{children}</ErrorBoundary>;
}
