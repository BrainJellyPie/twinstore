// Online stores workspace: build web shops from templates (or the store's own shelves), browse them the way a
// virtual shopper does — a screenshot with numbered options — tune their design, and run virtual shoppers with a
// purchase, browsing or bargain-hunting mission through one store or several variants at once.

import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BarChart3, ChevronDown, ChevronRight, Globe2, Loader2, MousePointerClick, Plus, Search, Settings2, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import { listRuns, listSites, listTemplates, onlineKeys, type OnlineRunStatus, type SiteSummary } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { searchText } from "@/shared/utils/searchText";
import { useAssistStore } from "@/stores/assistStore";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { onTabKeys } from "@/shared/utils/tabKeys";

import { BrowserView } from "./BrowserView";
import { RunLauncher } from "./RunLauncher";
import { RunReport } from "./RunReport";
import { SiteDesigner } from "./SiteDesigner";
import { TemplateGallery } from "./TemplateGallery";

type Tab = "browse" | "design" | "simulate";
const TABS: { id: Tab; label: MessageKey; icon: typeof Globe2 }[] = [
  { id: "browse", label: "onTabBrowse", icon: MousePointerClick },
  { id: "design", label: "onTabDesign", icon: Settings2 },
  { id: "simulate", label: "onTabSimulate", icon: Sparkles },
];

const busy = (run: OnlineRunStatus) => run.status === "pending" || run.status === "running";

export function OnlinePage({ projectId, initialSite, initialCompare, initialRun, initialShopper }: {
  projectId: string;
  /** A store to open, and a variant of it to start a comparison with (links from the marketing studio). */
  initialSite?: string; initialCompare?: string;
  /** A run's report to open, and a shopper's visit in it to play (links from a store's shopper page). */
  initialRun?: string; initialShopper?: { shopper: string; variant: number };
}) {
  const { t, locale } = useI18n();
  const [siteId, setSiteId] = useState<string | null>(initialSite ?? null);
  const [runId, setRunId] = useState<string | null>(initialRun ?? null);
  const [tab, setTab] = useState<Tab>(initialSite && initialCompare ? "simulate" : "browse");
  const [gallery, setGallery] = useState(false);
  const [wide, setWide] = useState(false);
  const [compare, setCompare] = useState<string | null>(initialCompare ?? null);
  // A design request typed in the command palette opens the designer, whose design chat takes it from there.
  const designAsk = useAssistStore((s) => s.pending?.projectId === projectId && s.pending.destination === "online_design");
  useEffect(() => {
    if (!designAsk) return;
    setRunId(null);
    setGallery(false);
    setTab("design");
  }, [designAsk]);

  // The address keeps the open store and run, so a reload or a copied link comes back to them. It is rewritten in
  // place, preserving this history entry's key so the route keeps the current editing state.
  useEffect(() => {
    const url = new URL(window.location.href);
    for (const key of ["site", "compare", "run", "shopper", "variant"]) url.searchParams.delete(key);
    if (siteId) url.searchParams.set("site", siteId);
    if (runId) url.searchParams.set("run", runId);
    if (url.href !== window.location.href) window.history.replaceState(window.history.state, "", url);
  }, [siteId, runId]);

  const project = useQuery({ queryKey: queryKeys.project(projectId), queryFn: ({ signal }) => api.getProject(projectId, signal) });
  const sites = useQuery({ queryKey: onlineKeys.sites(projectId), queryFn: ({ signal }) => listSites(projectId, signal) });
  const runs = useQuery({
    queryKey: onlineKeys.runs(projectId),
    queryFn: ({ signal }) => listRuns(projectId, signal),
    refetchInterval: (q) => (q.state.data?.some(busy) ? 1500 : false),
  });
  const templates = useQuery({ queryKey: onlineKeys.templates(), queryFn: ({ signal }) => listTemplates(signal), staleTime: Infinity });
  const currency = project.data?.metadata.currency ?? "USD";
  const list = sites.data ?? [];
  const selected = list.find((s) => s.id === siteId) ?? list[0] ?? null;
  const showGallery = gallery || (sites.isSuccess && list.length === 0);

  // On a narrow screen the store list sits above the work area; bring what was opened into view.
  const main = useRef<HTMLElement>(null);
  const reveal = () => {
    if (window.matchMedia?.("(max-width: 1023px)").matches) main.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  };
  const [picks, setPicks] = useState<string[]>([]);
  const [listOpen, setListOpen] = useState(false);
  // Variants sit under the store they were first copied from (copies of copies included), collapsed unless open.
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const rootOf = (site: SiteSummary): string => {
    const seen = new Set<string>();
    let current = site;
    while (current.variant_of && !seen.has(current.id)) {
      seen.add(current.id);
      const parent = list.find((p) => p.id === current.variant_of);
      if (!parent) break;
      current = parent;
    }
    return current.id;
  };
  // One box finds stores (a variant's group opens when the variant matches) and runs by name or note.
  const [find, setFind] = useState("");
  const needle = searchText(find);
  const found = (...texts: string[]) => !needle || texts.some((text) => searchText(text).includes(needle));
  const family = new Map<string, SiteSummary[]>();
  for (const s of list) {
    const root = rootOf(s);
    if (root !== s.id && found(s.name, s.note)) family.set(root, [...(family.get(root) ?? []), s]);
  }
  const roots = list.filter((s) => rootOf(s) === s.id && (found(s.name, s.note) || family.has(s.id)));
  const shownRuns = (runs.data ?? []).filter((r) => found(r.name, ...r.site_names));
  // The open store or run's entry is scrolled into the list's view when it opens (a link, a reload, a new store).
  const aside = useRef<HTMLElement>(null);
  // Set when a store or run is deleted: its Delete button held focus, which the entry now open takes.
  const refocus = useRef(false);
  const listsReady = sites.isSuccess && runs.isSuccess;
  useEffect(() => {
    const box = aside.current;
    const entry = box?.querySelector<HTMLElement>('[aria-current="true"]');
    if (refocus.current && entry) { refocus.current = false; entry.focus({ preventScroll: true }); }
    if (!box || !entry || !listsReady || box.scrollHeight <= box.clientHeight) return;
    const top = entry.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
    if (top < box.scrollTop || top + entry.offsetHeight > box.scrollTop + box.clientHeight) box.scrollTo?.({ top: top - box.clientHeight / 3 });
  }, [siteId, runId, listsReady, list.length]);
  const openSite = (id: string) => { setSiteId(id); setRunId(null); setGallery(false); setCompare(null); setPicks([]); setListOpen(false); reveal(); };

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden">
      <aside ref={aside} hidden={wide && !!runId} className="panel m-3 flex min-w-0 shrink-0 flex-col gap-4 rounded-[1.6rem] p-4 text-sm lg:mr-0 lg:w-[320px] lg:overflow-y-auto">
        <Link to="/projects/$pid" params={{ pid: projectId }} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3" aria-hidden /> {t("areaBackToStore")}
        </Link>
        <div>
          <h1 className="flex items-center gap-2 font-display text-2xl"><Globe2 className="size-5 text-primary" aria-hidden /> {t("onTitle")}</h1>
          <p className="mt-1 text-xs text-muted-foreground">{t("onSubtitle")}</p>
        </div>
        <Button onClick={() => { setGallery(true); setRunId(null); }}><Plus className="size-4" aria-hidden /> {t("onNewStore")}</Button>

        {/* On a phone the lists fold behind one button that says what is open, so the work area comes first. */}
        <button type="button" onClick={() => setListOpen((o) => !o)} aria-expanded={listOpen}
          className="flex items-center justify-between gap-2 rounded-xl border bg-card/60 px-3 py-2 text-left text-sm lg:hidden">
          <span className="min-w-0">
            <span className="block text-[0.7rem] font-semibold tracking-wide text-muted-foreground uppercase">{t("onListToggle", { stores: list.length, runs: runs.data?.length ?? 0 })}</span>
            <span className="block truncate font-medium">{runId ? (runs.data?.find((r) => r.run_id === runId)?.name ?? "") : selected?.name ?? ""}</span>
          </span>
          <ChevronDown className={cn("size-4 shrink-0 transition-transform", listOpen && "rotate-180")} aria-hidden />
        </button>
        <div className={cn("flex flex-col gap-4", !listOpen && "hidden lg:flex")} data-online-list>
        {(list.length > 6 || (runs.data?.length ?? 0) > 6) && (
          <label className="relative block">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <input type="search" value={find} onChange={(e) => setFind(e.target.value)} placeholder={t("onFind")} aria-label={t("onFind")}
              onKeyDown={(e) => {
                // Enter opens the first match, ↓ moves into the matches (not while an IME is composing).
                if (e.nativeEvent.isComposing || e.keyCode === 229 || (e.key !== "Enter" && e.key !== "ArrowDown")) return;
                const first = e.currentTarget.closest("[data-online-list]")?.querySelector<HTMLElement>("[data-online-result]");
                if (!first) return;
                e.preventDefault();
                if (e.key === "Enter") first.click(); else first.focus();
              }}
              className="h-8 w-full rounded-xl border bg-card/60 pr-2 pl-8 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/40" />
          </label>
        )}
        <section aria-labelledby="online-sites" className="space-y-2">
          <h2 id="online-sites" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("onStores")}</h2>
          {sites.isPending && <p className="text-xs text-muted-foreground">{t("studioLoading")}</p>}
          {sites.isError && <p role="alert" className="text-xs text-destructive">{sites.error.message}</p>}
          <ul className="space-y-1.5">
            {roots.map((root) => {
              const variants = family.get(root.id) ?? [];
              const expanded = !!needle || (open[root.id] ?? variants.some((v) => v.id === selected?.id));
              return (
                <li key={root.id} className="space-y-1">
                  <SiteButton site={root} active={!showGallery && !runId && selected?.id === root.id} onOpen={openSite}
                    searchResult={found(root.name, root.note)} />
                  {variants.length > 0 && (
                    <>
                      {!needle && <button type="button" aria-expanded={expanded} onClick={() => setOpen((o) => ({ ...o, [root.id]: !expanded }))}
                        className="ml-3 inline-flex items-center gap-1 rounded-lg px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">
                        <ChevronRight className={cn("size-3.5 transition-transform", expanded && "rotate-90")} aria-hidden />
                        {t("onVariantsCount", { count: variants.length })}
                      </button>}
                      {expanded && (
                        <ul className="ml-3 space-y-1 border-l pl-2">
                          {variants.map((v) => (
                            <li key={v.id}><SiteButton site={v} active={!showGallery && !runId && selected?.id === v.id} onOpen={openSite} compact /></li>
                          ))}
                        </ul>
                      )}
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        </section>

        <section aria-labelledby="online-runs" className="space-y-2">
          <h2 id="online-runs" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("onRuns")}</h2>
          {runs.data?.length === 0 && <p className="text-xs text-muted-foreground">{t("onNoRuns")}</p>}
          {needle && roots.length === 0 && shownRuns.length === 0 && <p className="text-xs text-muted-foreground">{t("onFindNone")}</p>}
          <ul className="space-y-1.5">
            {shownRuns.map((r) => (
              <li key={r.run_id}>
                <button type="button" data-online-result onClick={() => { setRunId(r.run_id); setGallery(false); setListOpen(false); reveal(); }}
                  aria-current={runId === r.run_id ? "true" : undefined}
                  className={cn("w-full rounded-xl border px-3 py-2 text-left transition-colors", runId === r.run_id ? "border-primary bg-primary/8" : "hover:bg-muted")}>
                  <span className="flex items-center gap-2 font-medium">
                    {busy(r) ? <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden /> : <BarChart3 className="size-3.5 shrink-0" aria-hidden />}
                    <span className="truncate" title={r.name || r.site_names.join(" vs ")}>{r.name || r.site_names.join(" vs ")}</span>
                  </span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {r.status === "failed" ? t("onRunFailed") : busy(r) ? t("onRunProgress", { done: r.done, total: r.total })
                      : t("onRunSummary", { shoppers: r.request.shoppers, stores: r.site_ids.length })}
                    {" · "}{new Date(r.created_at).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" })}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        </div>
      </aside>

      <main ref={main} className="m-3 flex min-h-[32rem] min-w-0 flex-1 scroll-mt-20 flex-col gap-3 lg:overflow-y-auto lg:[scrollbar-gutter:stable]">
        {runId ? (
          <RunReport key={`${projectId}:${runId}`} projectId={projectId} runId={runId} onDeleted={() => { refocus.current = true; setRunId(null); setWide(false); }}
            wide={wide} onWide={() => setWide((w) => !w)}
            initialJourney={runId === initialRun && initialShopper ? { ...initialShopper, play: true } : undefined}
            onTry={list.length ? (id, experiments) => {
              if (!list.some((s) => s.id === id)) return;
              openSite(id); setPicks(experiments); setTab("simulate");
            } : undefined} />
        ) : showGallery ? (
          <TemplateGallery
            projectId={projectId} currency={currency} templates={templates.data ?? []} loading={templates.isPending}
            error={templates.error?.message ?? null} setups={project.data?.setups ?? []}
            onCreated={(id) => { openSite(id); setTab("browse"); }}
            onCancel={list.length ? () => setGallery(false) : undefined}
          />
        ) : selected ? (
          <>
            <div className="panel flex flex-wrap items-center gap-2 rounded-[1.4rem] p-2" role="tablist" aria-label={t("onStoreTabs")}
              onKeyDown={(e) => onTabKeys(e, TABS.map((item) => item.id), tab, setTab)}>
              {TABS.map(({ id, label, icon: Icon }) => (
                <button key={id} type="button" role="tab" aria-selected={tab === id} tabIndex={tab === id ? 0 : -1}
                  onClick={() => { setSiteId(selected.id); setTab(id); }}
                  className={cn("flex h-9 items-center gap-2 rounded-xl px-3 text-sm font-medium", tab === id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>
                  <Icon className="size-4" aria-hidden /> {t(label)}
                </button>
              ))}
              <span className="ml-auto truncate px-2 text-sm font-semibold" title={selected.name}>{selected.name}</span>
            </div>
            {tab === "browse" && <BrowserView key={`${selected.id}:${selected.updated_at}`} projectId={projectId} siteId={selected.id} />}
            {tab === "design" && (
              <SiteDesigner key={selected.id} projectId={projectId} siteId={selected.id}
                onCopied={(id) => openSite(id)} onDeleted={() => { refocus.current = true; setSiteId(null); }}
                onTest={(id) => { setCompare(id); setTab("simulate"); }} />
            )}
            {tab === "simulate" && (
              <RunLauncher key={`${projectId}:${selected.id}:${compare ?? ""}:${picks.join()}`} projectId={projectId} sites={list} firstSiteId={selected.id}
                initialPicked={picks}
                compareWith={compare && list.some((s) => s.id === compare) ? compare : undefined}
                hasCustomers={(project.data?.personas.length ?? 0) > 0}
                onStarted={(id) => { setRunId(id); }} />
            )}
          </>
        ) : (
          <div className="panel flex flex-1 items-center justify-center rounded-[1.6rem] p-6 text-sm text-muted-foreground">
            {sites.isPending ? t("studioLoading") : t("onEmpty")}
          </div>
        )}
      </main>
    </div>
  );
}

function SiteButton({ site, active, onOpen, compact = false, searchResult = true }: {
  site: SiteSummary; active: boolean; onOpen: (id: string) => void; compact?: boolean; searchResult?: boolean;
}) {
  const { t } = useI18n();
  return (
    <button data-online-result={searchResult ? "" : undefined} type="button" onClick={() => onOpen(site.id)} aria-current={active ? "true" : undefined}
      className={cn("w-full rounded-xl border text-left transition-colors", compact ? "px-2.5 py-1.5" : "px-3 py-2",
        active ? "border-primary bg-primary/8" : "hover:bg-muted")}>
      <span className={cn("flex items-center gap-2 font-medium", compact && "text-[0.8rem]")}>
        <span className="size-3 shrink-0 rounded-full ring-1 ring-foreground/25 dark:ring-foreground/55" style={{ background: site.theme_color }} aria-hidden />
        <span className="truncate" title={site.name}>{site.name}</span>
      </span>
      {!compact && <span className="mt-0.5 block text-xs text-muted-foreground">{t("onStoreStats", { products: site.products, categories: site.categories })}</span>}
      {site.note && <span className="mt-0.5 block truncate text-xs text-muted-foreground" title={site.note}>{site.note}</span>}
    </button>
  );
}
