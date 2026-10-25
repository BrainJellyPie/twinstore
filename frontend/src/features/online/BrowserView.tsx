// Browse a store exactly as a virtual shopper sees it: the server's screenshot with a numbered badge on every
// clickable element, the same options as a list, and what a text model reads instead of the picture.

import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Monitor, RotateCcw, Shuffle, Smartphone, UserCheck } from "lucide-react";

import { browse, VISIONS, type BrowserState, type Device, type PageOption, type PageView, type Vision } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

import { ACTION_LABELS, PAGE_LABELS, VISION_LABELS } from "./labels";

interface Step { state: BrowserState | null; option?: number; query?: string; markSeed: number; device: Device; vision: Vision }

export function BrowserView({ projectId, siteId }: { projectId: string; siteId: string }) {
  const { t } = useI18n();
  const [view, setView] = useState<PageView | null>(null);
  const [device, setDevice] = useState<Device>("desktop");
  const [hasAccount, setHasAccount] = useState(false);
  const [markSeed, setMarkSeed] = useState(0);
  const [vision, setVision] = useState<Vision>("typical");
  const [searching, setSearching] = useState<PageOption | null>(null);
  const [query, setQuery] = useState("");
  const [clicks, setClicks] = useState<string[]>([]);
  const searchRef = useRef<HTMLInputElement>(null);
  const go = useMutation({
    mutationFn: (step: Step) => browse(projectId, siteId, {
      state: step.state, option: step.option ?? null, query: step.query ?? "", mark_seed: step.markSeed,
      has_account: hasAccount, device: step.device, vision: step.vision,
    }),
    onSuccess: (next, step) => {
      setView(next); setMarkSeed(step.markSeed); setDevice(step.device); setVision(step.vision); setSearching(null); setQuery("");
      if (step.state === null) setClicks([]);
    },
  });
  const start = go.mutate;
  useEffect(() => { start({ state: null, markSeed: 0, device: "desktop", vision: "typical" }); }, [start]);
  const newVisit = (next: Device) => go.mutate({ state: null, markSeed, device: next, vision });
  const renumber = (on: boolean) => {
    const seed = on ? 1 + Math.floor(Math.random() * 1e6) : 0;
    go.mutate({ state: view?.state ?? null, markSeed: seed, device, vision });
  };
  const seeAs = (next: Vision) => go.mutate({ state: view?.state ?? null, markSeed, device, vision: next });
  useEffect(() => { if (searching) searchRef.current?.focus(); }, [searching]);

  const use = (option: PageOption) => {
    if (!view || go.isPending) return;
    if (option.kind === "search") {
      setSearching(option);
      return;
    }
    setClicks((c) => [...c.slice(-30), `${t(PAGE_LABELS[view.page])} → [${option.number}] ${option.label}`]);
    go.mutate({ state: view.state, option: option.number, markSeed, device, vision });
  };
  const submitSearch = () => {
    if (!view || !searching || !query.trim() || go.isPending) return;
    setClicks((c) => [...c.slice(-30), `${t(PAGE_LABELS[view.page])} → [${searching.number}] “${query.trim()}”`]);
    go.mutate({ state: view.state, option: searching.number, query: query.trim(), markSeed, device, vision });
  };

  return (
    <div className="grid min-h-0 gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
      <section className="panel flex min-w-0 flex-col gap-3 rounded-[1.6rem] p-3" aria-label={t("onBrowserLabel")}>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="inline-flex rounded-md border p-0.5" role="group" aria-label={t("onDevice")}>
            {(["desktop", "mobile"] as Device[]).map((d) => (
              <button key={d} type="button" aria-pressed={device === d} onClick={() => newVisit(d)} disabled={go.isPending}
                className={cn("flex items-center gap-1 rounded px-2 py-1", device === d ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
                {d === "desktop" ? <Monitor className="size-3.5" aria-hidden /> : <Smartphone className="size-3.5" aria-hidden />}
                {t(d === "desktop" ? "onDeviceDesktop" : "onDeviceMobile")}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={hasAccount} onChange={(e) => setHasAccount(e.target.checked)} />
            <UserCheck className="size-3.5" aria-hidden /> {t("onHasAccount")}
          </label>
          <label className="flex items-center gap-1.5" title={t("onShuffleHint")}>
            <input type="checkbox" checked={markSeed !== 0} onChange={(e) => renumber(e.target.checked)} disabled={go.isPending} />
            <Shuffle className="size-3.5" aria-hidden /> {t("onShuffle")}
          </label>
          <label className="flex items-center gap-1.5" title={t("onSeeAsHint")}>
            {t("onSeeAs")}
            <select className="h-7 rounded-md border bg-background px-1.5" value={vision} disabled={go.isPending}
              onChange={(e) => seeAs(e.target.value as Vision)}>
              {VISIONS.map((v) => <option key={v} value={v}>{t(VISION_LABELS[v])}</option>)}
            </select>
          </label>
          <Button variant="outline" size="xs" className="ml-auto" onClick={() => newVisit(device)} disabled={go.isPending}>
            <RotateCcw aria-hidden /> {t("onNewVisit")}
          </Button>
        </div>
        {go.error && <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">{go.error.message}</p>}
        {view ? (
          <div className={cn("relative mx-auto w-full overflow-hidden rounded-xl border bg-white shadow-sm", view.width < 500 ? "max-w-[430px]" : "max-w-[1024px]")}>
            <img src={view.image} alt={t("onScreenshotAlt", { title: view.title })} className="block w-full select-none" draggable={false} />
            {view.options.map((o) => o.box && (
              <button key={o.number} type="button" onClick={() => use(o)} title={`[${o.number}] ${o.label}`} aria-label={`${o.number}. ${o.label}`}
                tabIndex={-1}
                className="absolute rounded-md outline-primary transition-colors hover:bg-primary/15 hover:outline-2"
                style={{
                  left: `${(o.box[0] / view.width) * 100}%`, top: `${(o.box[1] / view.height) * 100}%`,
                  width: `${((o.box[2] - o.box[0]) / view.width) * 100}%`, height: `${((o.box[3] - o.box[1]) / view.height) * 100}%`,
                }} />
            ))}
            {go.isPending && <div className="absolute inset-0 grid place-items-center bg-white/40"><Loader2 className="size-8 animate-spin text-primary" aria-label={t("studioLoading")} /></div>}
          </div>
        ) : (
          <div className="grid h-96 place-items-center text-sm text-muted-foreground">{go.isPending ? t("studioLoading") : t("onNoPage")}</div>
        )}
      </section>

      <aside className="panel flex min-w-0 flex-col gap-3 rounded-[1.6rem] p-3 text-sm xl:max-h-[calc(100vh-10rem)] xl:overflow-y-auto">
        {view && (
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">{t(PAGE_LABELS[view.page])}</div>
            <div className="truncate font-mono text-xs" title={view.url}>{view.url}</div>
          </div>
        )}
        {searching && (
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); submitSearch(); }}>
            <Input ref={searchRef} value={query} maxLength={60} onChange={(e) => setQuery(e.target.value)} placeholder={t("onTypeSearch")} aria-label={t("onTypeSearch")} />
            <Button type="submit" size="sm" disabled={!query.trim() || go.isPending}>{t("onSearchGo")}</Button>
          </form>
        )}
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("onOptions", { count: view?.options.length ?? 0 })}</h3>
          <ol className="space-y-1">
            {view?.options.map((o) => (
              <li key={o.number}>
                <button type="button" onClick={() => use(o)} disabled={go.isPending}
                  className="flex w-full items-start gap-2 rounded-lg px-1.5 py-1 text-left text-xs hover:bg-muted disabled:opacity-60">
                  <span className="mt-px shrink-0 rounded bg-rose-600 px-1.5 font-mono font-bold text-white">{o.number}</span>
                  <span className="min-w-0">
                    <span className="block text-muted-foreground">{t(ACTION_LABELS[o.kind])}</span>
                    <span className="block break-words">{o.label}</span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </div>
        {view && (
          <details className="rounded-lg border p-2 text-xs">
            <summary className="cursor-pointer font-medium">{t("onOutline")}</summary>
            <p className="mt-1 text-muted-foreground">{t("onOutlineHint")}</p>
            <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-[0.7rem]">{view.outline.join("\n")}</pre>
          </details>
        )}
        {clicks.length > 0 && (
          <details className="rounded-lg border p-2 text-xs" open>
            <summary className="cursor-pointer font-medium">{t("onYourClicks", { count: clicks.length })}</summary>
            <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-muted-foreground">{clicks.map((c, i) => <li key={i}>{c}</li>)}</ol>
          </details>
        )}
      </aside>
    </div>
  );
}
