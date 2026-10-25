// A corner notice when a run of the current (or last-used) store finishes or fails while the person is elsewhere in
// the app, with the way to its results: an online run off its report, or a store run off the floor page (where the
// run's own view shows the result).

import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, TriangleAlert, X } from "lucide-react";

import { useProjectRuns } from "@/features/runs/hooks";
import type { RunListItem } from "@/shared/api/client";
import { listRuns, onlineKeys, type OnlineRunStatus } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { queryKeys } from "@/shared/queries/keys";
import { useProjects } from "@/shared/queries/useProjects";
import { useSimulationStore } from "@/stores/simulationStore";

import { projectIdFromPath, rememberedStore } from "./paths";

const running = (run: { status: string }) => run.status === "pending" || run.status === "running";

interface Finished { storeId: string; online: boolean; runId: string; setupId: string; name: string; failed: boolean }

export function RunNotice() {
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
  useProjectRuns(storeId ?? "", !!storeId);
  const [done, setDone] = useState<Finished | null>(null);
  useEffect(() => {
    if (!storeId) return;
    const onlineKey = JSON.stringify(onlineKeys.runs(storeId));
    const storeKey = JSON.stringify(queryKeys.projectRuns(storeId));
    const statuses = (list: { run_id: string; status: string }[] | undefined) => new Map((list ?? []).map((run) => [run.run_id, run.status]));
    const before = new Map([
      [onlineKey, statuses(qc.getQueryData<OnlineRunStatus[]>(onlineKeys.runs(storeId)))],
      [storeKey, statuses(qc.getQueryData<RunListItem[]>(queryKeys.projectRuns(storeId)))],
    ]);
    return qc.getQueryCache().subscribe((event) => {
      const key = JSON.stringify(event.query.queryKey);
      if (event.type !== "updated" || event.action.type !== "success" || !before.has(key)) return;
      const list = event.query.state.data as (OnlineRunStatus | RunListItem)[];
      const was = before.get(key)!;
      const finished = list.find((run) => !running(run) && running({ status: was.get(run.run_id) ?? "" }));
      before.set(key, statuses(list));
      if (!finished) return;
      const online = key === onlineKey;
      const { pathname, search } = window.location;
      // The run's own view is on screen and shows the result itself: its report, or the store's floor page.
      if (online ? pathname.startsWith("/online/") && new URLSearchParams(search).get("run") === finished.run_id
        : pathname.replace(/\/$/, "") === `/projects/${storeId}`) return;
      const name = "site_names" in finished ? finished.name || finished.site_names.join(" vs ")
        : new Date(finished.created_at).toLocaleString();
      setDone({ storeId, online, runId: finished.run_id, setupId: "setup_id" in finished ? finished.setup_id : "",
        name, failed: finished.status === "failed" });
    });
  }, [qc, storeId]);
  useEffect(() => {
    if (!done) return;
    const timer = window.setTimeout(() => setDone(null), 20_000);
    return () => window.clearTimeout(timer);
  }, [done]);

  if (!done) return null;
  const { failed } = done;
  const open = () => {
    setDone(null);
    if (done.online) {
      void navigate({ to: "/online/$pid", params: { pid: done.storeId }, search: { run: done.runId } });
      return;
    }
    const simulation = useSimulationStore.getState();
    simulation.setSelectedSetupId(done.setupId);
    simulation.setViewRunId(done.runId);
    simulation.setActiveTab("dashboard");
    void navigate({ to: "/projects/$pid", params: { pid: done.storeId } });
  };
  return (
    <div role="status" className="fixed right-4 bottom-4 z-50 border bg-card flex w-[min(22rem,calc(100vw-2rem))] items-start gap-3 rounded-2xl p-3 text-sm shadow-[var(--shadow-lift)] animate-rise">
      <span className={failed ? "mt-0.5 text-negative" : "mt-0.5 text-positive"} aria-hidden>
        {failed ? <TriangleAlert className="size-5" /> : <CircleCheck className="size-5" />}
      </span>
      <div className="min-w-0 flex-1 space-y-2">
        <div>
          <p className="font-medium">{t(done.online ? (failed ? "onRunNoticeFailed" : "onRunNoticeDone") : (failed ? "storeRunNoticeFailed" : "storeRunNoticeDone"))}</p>
          <p className="truncate text-xs text-muted-foreground">{done.name}</p>
        </div>
        <Button size="sm" onClick={open}>{t(done.online ? "onRunNoticeOpen" : "storeRunNoticeOpen")}</Button>
      </div>
      <button type="button" onClick={() => setDone(null)} aria-label={t("hideNotice")}
        className="grid size-7 shrink-0 place-items-center rounded-lg text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground">
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}
