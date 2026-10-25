// A corner notice when an online run of the current (or last-used) store finishes or fails while the person is
// elsewhere in the app, with the way to its report. Nothing shows for the run already open on the online page.

import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, TriangleAlert, X } from "lucide-react";

import { listRuns, onlineKeys, type OnlineRunStatus } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { useProjects } from "@/shared/queries/useProjects";

import { projectIdFromPath, rememberedStore } from "./paths";

const running = (run: OnlineRunStatus) => run.status === "pending" || run.status === "running";

export function OnlineRunNotice() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pathname = useLocation({ select: (location) => location.pathname });
  const { data: projects } = useProjects();
  const storeId = projectIdFromPath(pathname) ?? rememberedStore(projects);
  // Polls only while a run is going; the online page shares this list.
  useQuery({
    queryKey: onlineKeys.runs(storeId ?? ""), queryFn: ({ signal }) => listRuns(storeId!, signal), enabled: !!storeId,
    refetchInterval: (query) => (query.state.data?.some(running) ? 3000 : false),
  });
  const [done, setDone] = useState<{ storeId: string; run: OnlineRunStatus } | null>(null);
  useEffect(() => {
    if (!storeId) return;
    const key = JSON.stringify(onlineKeys.runs(storeId));
    const statuses = (list: OnlineRunStatus[] | undefined) => new Map((list ?? []).map((run) => [run.run_id, run.status]));
    let before = statuses(qc.getQueryData<OnlineRunStatus[]>(onlineKeys.runs(storeId)));
    return qc.getQueryCache().subscribe((event) => {
      if (event.type !== "updated" || event.action.type !== "success" || JSON.stringify(event.query.queryKey) !== key) return;
      const list = event.query.state.data as OnlineRunStatus[];
      const finished = list.find((run) => !running(run) && (before.get(run.run_id) === "pending" || before.get(run.run_id) === "running"));
      before = statuses(list);
      // The report of that run is already on screen: it shows the result itself.
      const open = new URLSearchParams(window.location.search).get("run");
      if (finished && !(window.location.pathname.startsWith("/online/") && open === finished.run_id)) setDone({ storeId, run: finished });
    });
  }, [qc, storeId]);
  useEffect(() => {
    if (!done) return;
    const timer = window.setTimeout(() => setDone(null), 20_000);
    return () => window.clearTimeout(timer);
  }, [done]);

  if (!done) return null;
  const failed = done.run.status === "failed";
  return (
    <div role="status" className="fixed right-4 bottom-4 z-50 border bg-card flex w-[min(22rem,calc(100vw-2rem))] items-start gap-3 rounded-2xl p-3 text-sm shadow-[var(--shadow-lift)] animate-rise">
      <span className={failed ? "mt-0.5 text-negative" : "mt-0.5 text-positive"} aria-hidden>
        {failed ? <TriangleAlert className="size-5" /> : <CircleCheck className="size-5" />}
      </span>
      <div className="min-w-0 flex-1 space-y-2">
        <div>
          <p className="font-medium">{t(failed ? "onRunNoticeFailed" : "onRunNoticeDone")}</p>
          <p className="truncate text-xs text-muted-foreground">{done.run.name || done.run.site_names.join(" vs ")}</p>
        </div>
        <Button size="sm" onClick={() => {
          setDone(null);
          void navigate({ to: "/online/$pid", params: { pid: done.storeId }, search: { run: done.run.run_id } });
        }}>{t("onRunNoticeOpen")}</Button>
      </div>
      <button type="button" onClick={() => setDone(null)} aria-label={t("hideNotice")}
        className="grid size-7 shrink-0 place-items-center rounded-lg text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground">
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}
