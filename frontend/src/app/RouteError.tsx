// What a page shows instead of its content when it cannot: a route that failed to load (after an update that is a
// script of the previous version, the page reloads once), an address that matches no page, and a store that no longer
// exists. Each says what happened in the selected language and offers a way back.

import { useEffect, useState, type ReactNode } from "react";
import { useNavigate, useRouter, type ErrorComponentProps } from "@tanstack/react-router";
import { CircleAlert, SearchX, Store } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";

import { isStaleBuildError, reloadForNewVersion, type StaleCheck } from "./staleBuild";

function Problem({ icon: Icon, title, hint, detail, children }: { icon: LucideIcon; title: string; hint?: string; detail?: string; children?: ReactNode }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto p-4">
      <div role="alert" className="panel my-auto w-full max-w-md shrink-0 space-y-3 self-center rounded-[1.6rem] p-6 text-center [overflow-wrap:anywhere]">
        <span className="mx-auto grid size-12 place-items-center rounded-2xl heat-gradient text-white dark:text-neutral-950 shadow-[0_8px_24px_-8px_var(--heat-2)]" aria-hidden>
          <Icon className="size-5" />
        </span>
        <h2 className="font-display text-xl tracking-[-0.02em]">{title}</h2>
        {hint && <p className="text-sm text-muted-foreground">{hint}</p>}
        {detail && (
          <details className="text-left text-xs text-muted-foreground">
            <summary className="cursor-pointer text-center">{t("problemDetails")}</summary>
            <p className="mt-2 max-h-40 overflow-y-auto rounded-lg bg-foreground/[0.04] p-2 font-mono whitespace-pre-wrap">{detail}</p>
          </details>
        )}
        <div className="flex flex-wrap justify-center gap-2 pt-1">
          <Button size="sm" onClick={() => void navigate({ to: "/" })}>{t("backToStores")}</Button>
          {children}
        </div>
      </div>
    </div>
  );
}

export function RouteError({ error, reset }: ErrorComponentProps) {
  const { t } = useI18n();
  const router = useRouter();
  const message = error instanceof Error ? error.message : String(error);
  const stale = isStaleBuildError(error);
  const [check, setCheck] = useState<{ message: string; result: StaleCheck } | null>(null);
  useEffect(() => {
    if (!stale) return;
    let live = true;
    void reloadForNewVersion().then((result) => { if (live) setCheck({ message, result }); });
    return () => { live = false; };
  }, [stale, message]);
  if (stale && (check?.message !== message || check.result === "reloading")) return null;
  if (error instanceof ApiError && error.status === 404) return <StoreMissing detail={error.message} />;
  // The page's script could not be fetched because the backend is stopped or restarting: once it answers, a reload loads it.
  const offline = stale && check?.result === "offline";
  return (
    <Problem icon={CircleAlert} title={t(offline ? "backendOffline" : "routeErrorTitle")} hint={offline ? t("routeServerDownHint") : undefined}
      detail={message}>
      <Button size="sm" variant="outline" onClick={() => {
        if (offline) void reloadForNewVersion().then((result) => setCheck({ message, result }));
        else { reset(); void router.invalidate(); }
      }}>{t("tryAgain")}</Button>
    </Problem>
  );
}

export function NotFound() {
  const { t } = useI18n();
  return <Problem icon={SearchX} title={t("pageNotFoundTitle")} hint={t("pageNotFoundHint")} />;
}

export function StoreMissing({ detail }: { detail?: string }) {
  const { t } = useI18n();
  return <Problem icon={Store} title={t("storeMissingTitle")} hint={t("storeMissingHint")} detail={detail} />;
}
