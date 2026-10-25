// ⌘K / Ctrl+K (or "/") command palette: jump to any store or page, or flip the theme, from the
// keyboard. Arrow keys move, Enter runs, Esc closes.

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Camera,
  CornerDownLeft,
  Globe2,
  KeyRound,
  LayoutGrid,
  Map,
  Megaphone,
  Moon,
  Plus,
  Power,
  Loader2,
  Search,
  Sparkles,
  Store,
  Sun,
  X,
} from "lucide-react";

import * as api from "@/shared/api/client";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import { translate, useI18n } from "@/shared/i18n/i18n";
import { LOCALES, type MessageKey } from "@/shared/i18n/messages";
import { storeTypeLabel } from "@/shared/i18n/storeLabels";
import { queryKeys } from "@/shared/queries/keys";
import { useProjects } from "@/shared/queries/useProjects";
import { cn } from "@/shared/utils/cn";
import { searchText } from "@/shared/utils/searchText";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";

import { useCommandPalette } from "./commandPalette";
import { quitLauncher, useLauncher } from "./launcher";
import { projectIdFromPath } from "./paths";
import { useTheme } from "./theme";

interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  aliases?: string;
  icon: typeof Store;
  run: () => void;
}

type LocalizedCommand = Omit<Command, "group" | "label" | "hint"> & { group: MessageKey; label: MessageKey; hint?: MessageKey };

function isComposing(event: KeyboardEvent) {
  // Some IMEs report 229 on the final composition key without isComposing.
  return event.isComposing || event.keyCode === 229;
}

function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

function matches(command: Command, query: string): boolean {
  const hay = searchText(`${command.label} ${command.hint ?? ""} ${command.group} ${command.aliases ?? ""} ${command.id}`);
  return searchText(query)
    .split(" ")
    .filter(Boolean)
    .every((token) => hay.includes(token));
}

// Run questions are answered in a finished run's playback: keep the layout in view when it shows one,
// else pick the most recently finished layout. null when no layout has a run.
function layoutForRunQuestion(layouts: api.SetupSummary[], selectedSetupId: string | null, viewRunId: string | null): string | null {
  const ordered = [...layouts].sort((a, b) => a.created_at.localeCompare(b.created_at));
  const current = ordered.find((layout) => layout.id === selectedSetupId) ?? ordered[0];
  if (current && (current.runId || (current.id === selectedSetupId && viewRunId))) return current.id;
  return ordered.filter((layout) => layout.runId).sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0]?.id ?? null;
}

function PaletteBody({ onDone }: { onDone: () => void }) {
  const { locale, t } = useI18n();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { pathname } = useLocation();
  const pid = projectIdFromPath(pathname);
  const open = useCommandPalette((s) => s.open);
  const { data: projects } = useProjects();
  const { theme, setTheme } = useTheme();
  const launched = useLauncher();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const itemRefs = useRef(new globalThis.Map<number, HTMLButtonElement>());

  const commands = useMemo<Command[]>(() => {
    const localize = (command: LocalizedCommand): Command => ({
      ...command,
      group: translate(locale, command.group), label: translate(locale, command.label),
      hint: command.hint ? translate(locale, command.hint) : undefined,
      aliases: LOCALES.map(({ code }) => `${translate(code, command.group)} ${translate(code, command.label)} ${command.hint ? translate(code, command.hint) : ""}`).join(" "),
    });
    const go = (to: string, params?: Record<string, string>) => () => navigate({ to, params });
    const list: Command[] = [];
    if (pid) {
      list.push(
        localize({ id: "floor", group: "commandThisStore", label: "commandFloor", hint: "commandFloorHint", icon: Store, run: go("/projects/$pid", { pid }) }),
        localize({ id: "area", group: "commandThisStore", label: "neighborhood", hint: "commandAreaHint", icon: Map, run: go("/town/$pid", { pid }) }),
        localize({ id: "capture", group: "commandThisStore", label: "shelfCapture", hint: "commandCaptureHint", icon: Camera, run: go("/capture/$pid", { pid }) }),
        localize({ id: "marketing", group: "commandThisStore", label: "marketingStudio", hint: "commandMarketingHint", icon: Megaphone, run: go("/marketing/$pid", { pid }) }),
        localize({ id: "online", group: "commandThisStore", label: "onlineStores", hint: "commandOnlineHint", icon: Globe2, run: go("/online/$pid", { pid }) }),
      );
    }
    list.push(
      localize({ id: "home", group: "commandGoTo", label: "allStores", hint: "commandHomeHint", icon: LayoutGrid, run: go("/") }),
      localize({ id: "new", group: "commandGoTo", label: "newStore", hint: "commandNewHint", icon: Plus, run: go("/projects/new") }),
      localize({ id: "models", group: "commandGoTo", label: "modelProviders", hint: "commandModelsHint", icon: KeyRound, run: go("/settings") }),
    );
    for (const p of projects ?? []) {
      list.push({
        id: `store-${p.project_id}`,
        group: translate(locale, "stores"),
        label: p.name || translate(locale, "untitledStore"),
        hint: storeTypeLabel(p.store_type, locale),
        aliases: `${p.store_type} ${LOCALES.map(({ code }) => storeTypeLabel(p.store_type, code)).join(" ")}`,
        icon: Store,
        run: go("/projects/$pid", { pid: p.project_id }),
      });
    }
    list.push(
      theme === "dark"
        ? localize({ id: "theme", group: "commandAppearance", label: "switchDay", hint: "commandLightHint", icon: Sun, run: () => setTheme("light") })
        : localize({ id: "theme", group: "commandAppearance", label: "switchNight", hint: "commandDarkHint", icon: Moon, run: () => setTheme("dark") }),
    );
    if (launched) {
      list.push(localize({ id: "quit", group: "commandApp", label: "quitTwinStore", hint: "commandQuitHint", icon: Power, run: () => void quitLauncher({ title: translate(locale, "quitStoppedTitle"), body: translate(locale, "quitStoppedBody") }) }));
    }
    return list;
  }, [navigate, pid, projects, theme, setTheme, launched, locale]);

  // A sentence typed in a store's palette can be handed to the right tool, which drafts from the same words.
  const [asking, setAsking] = useState(false);
  const [askNote, setAskNote] = useState<string | null>(null);
  const requestId = useRef(0);
  useLayoutEffect(() => {
    requestId.current += 1;
    setAsking(false);
    setAskNote(null);
    return () => { requestId.current += 1; };
  }, [query, pid, open]);
  const sendAsk = useAssistStore((s) => s.send);
  const setActiveTab = useSimulationStore((s) => s.setActiveTab);
  const text = query.trim();
  const sentence = text.split(/\s+/).filter(Boolean).length >= 3
    || /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u.test(text);
  const canAsk = !!pid && sentence && Array.from(text).length >= 3;
  const ask = async () => {
    if (!open || !pid || !canAsk || asking) return;
    const id = ++requestId.current;
    setAsking(true);
    setAskNote(null);
    try {
      const hasRun = projects?.find((p) => p.project_id === pid)?.status === "Simulated";
      const route = await api.routeAssist({ text, has_run: hasRun });
      if (id !== requestId.current) return;
      if (route.destination === "none") {
        setAskNote(t("commandAskNone"));
        return;
      }
      if (route.destination === "run_question") {
        const layouts = await qc.ensureQueryData({ queryKey: queryKeys.setups(pid), queryFn: ({ signal }) => api.getSetups(pid, signal) });
        if (id !== requestId.current) return;
        const { selectedSetupId, viewRunId, setSelectedSetupId } = useSimulationStore.getState();
        const layoutId = layoutForRunQuestion(layouts, selectedSetupId, viewRunId);
        if (!layoutId) {
          setAskNote(t("commandAskNoRun"));
          return;
        }
        if (layoutId !== selectedSetupId) setSelectedSetupId(layoutId);
      }
      sendAsk({ projectId: pid, destination: route.destination, text });
      if (route.destination === "run_question") setActiveTab("dashboard");
      if (route.destination === "layout_edit") setActiveTab("settings");
      if (route.destination === "find_shoppers") setActiveTab("shoppers");
      onDone();
      const onFloor = ["run_question", "layout_edit", "find_shoppers", "optimize"].includes(route.destination);
      const to = route.destination === "area" ? "/town/$pid" : route.destination === "online_design" ? "/online/$pid"
        : onFloor ? "/projects/$pid" : "/marketing/$pid";
      void navigate({ to, params: { pid } });
    } catch (e) {
      if (id === requestId.current) setAskNote(e instanceof Error ? e.message : String(e));
    } finally {
      if (id === requestId.current) setAsking(false);
    }
  };
  const visible = useMemo(() => {
    const found = commands.filter((c) => matches(c, query));
    // A sentence that names no command can be asked; command words keep their commands.
    if (!canAsk || found.length > 0) return found;
    // Running it is handled in `run` (the palette stays open while the request is routed).
    const askCommand: Command = {
      id: "ask", group: t("commandAsk"), label: `“${text}”`, hint: t("commandAskHint"), icon: Sparkles, run: () => {},
    };
    return [askCommand];
  }, [commands, query, canAsk, text, t]);
  const current = Math.min(active, Math.max(visible.length - 1, 0));

  useEffect(() => {
    itemRefs.current.get(current)?.scrollIntoView({ block: "nearest" });
  }, [current, visible]);

  const run = (command: Command | undefined) => {
    if (!command) return;
    if (command.id === "ask") {
      void ask();
      return;
    }
    onDone();
    command.run();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (isComposing(e.nativeEvent)) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((current + 1) % Math.max(visible.length, 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((current - 1 + visible.length) % Math.max(visible.length, 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(visible[current]);
    }
  };

  let lastGroup = "";
  return (
    <div className="flex min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-3 border-b px-5">
        <Search className="size-5 shrink-0 text-muted-foreground" aria-hidden />
        <input
          value={query}
          onKeyDown={onKeyDown}
          onChange={(e) => {
            setQuery(Array.from(e.target.value).slice(0, 500).join(""));
            setActive(0);
          }}
          placeholder={t("commandPlaceholder")}
          className="h-16 min-w-0 flex-1 bg-transparent text-lg tracking-[-0.01em] outline-none placeholder:text-muted-foreground/70"
          aria-label={t("command")}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded
          aria-controls="command-list"
          aria-activedescendant={visible[current] ? `cmd-${visible[current].id}` : undefined}
        />
        <kbd className="num hidden rounded-md border px-1.5 py-0.5 text-[0.7rem] text-muted-foreground sm:block">esc</kbd>
        <button type="button" onClick={onDone} aria-label={t("close")} title={t("close")}
          className="grid size-10 shrink-0 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground">
          <X className="size-4" aria-hidden />
        </button>
      </div>
      <div id="command-list" role="listbox" aria-label={t("commandResults")} className="min-h-0 max-h-[min(26rem,60vh)] overflow-y-auto p-2">
        {visible.length === 0 && (
          <p role="status" className="break-words px-3 py-10 text-center text-sm text-muted-foreground">{t("commandNoMatches", { query })}</p>
        )}
        {askNote && <p role="status" className="mx-3 mb-1 rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">{askNote}</p>}
        {pid && !query.trim() && <p className="mx-3 mb-1 flex items-start gap-1.5 rounded-lg bg-primary/[0.05] px-3 py-2 text-xs text-muted-foreground"><Sparkles className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />{t("commandAskTip")}</p>}
        {visible.map((c, i) => {
          const header = c.group !== lastGroup ? c.group : null;
          lastGroup = c.group;
          const Icon = c.icon;
          const isActive = i === current;
          return (
            <div key={c.id}>
              {header && <div className="eyebrow px-3 pt-3 pb-1.5">{header}</div>}
              <button
                id={`cmd-${c.id}`}
                ref={(el) => {
                  if (el) itemRefs.current.set(i, el);
                  else itemRefs.current.delete(i);
                }}
                type="button"
                role="option"
                tabIndex={-1}
                aria-selected={isActive}
                onMouseMove={() => setActive(i)}
                onClick={() => run(c)}
                className={cn(
                  "relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors",
                  isActive ? "bg-foreground/[0.07] text-foreground" : "text-foreground/85",
                )}
              >
                {isActive && <span className="absolute top-2 bottom-2 left-0 w-[3px] rounded-full bg-primary" aria-hidden />}
                <span
                  className={cn(
                    "grid size-8 shrink-0 place-items-center rounded-lg border transition-colors",
                    isActive ? "border-transparent bg-primary text-primary-foreground" : "bg-foreground/[0.03] text-muted-foreground",
                  )}
                >
                  {c.id === "ask" && asking ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Icon className="size-4" aria-hidden />}
                </span>
                <span className="min-w-0 flex-1">
                  <span title={c.label} className="block truncate text-[0.95rem] font-medium">{c.label}</span>
                  {c.hint && <span className="block truncate text-xs text-muted-foreground">{c.id === "ask" && asking ? t("commandAsking") : c.hint}</span>}
                </span>
                {isActive ? (
                  <CornerDownLeft className="size-4 text-muted-foreground" aria-hidden />
                ) : (
                  <ArrowRight className="size-4 text-muted-foreground/0" aria-hidden />
                )}
              </button>
            </div>
          );
        })}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-t px-5 py-2.5 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <kbd className="num rounded border px-1">↑</kbd>
          <kbd className="num rounded border px-1">↓</kbd> {t("commandMove")}
        </span>
        <span className="flex items-center gap-1.5">
          <kbd className="num rounded border px-1">↵</kbd> {t("commandOpen")}
        </span>
        <span className="ml-auto aurora-text font-medium">twinstore</span>
      </div>
    </div>
  );
}

export function CommandPalette() {
  const { t } = useI18n();
  const returnFocus = useRef<HTMLElement | null>(null);
  const open = useCommandPalette((s) => s.open);
  const setOpen = useCommandPalette((s) => s.setOpen);
  const toggle = useCommandPalette((s) => s.toggle);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isComposing(e)) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        toggle();
      } else if (e.key === "/" && !e.metaKey && !e.ctrlKey && !isTypingTarget(e.target)) {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen, toggle]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        showCloseButton={false}
        onOpenAutoFocus={() => { returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (returnFocus.current?.isConnected) returnFocus.current.focus();
        }}
        onEscapeKeyDown={(event) => { if (isComposing(event)) event.preventDefault(); }}
        className="ring-aurora top-4 flex max-h-[calc(100dvh-2rem)] max-w-[calc(100%-2rem)] translate-y-0 flex-col gap-0 overflow-hidden p-0 sm:top-[14vh] sm:max-h-[80dvh] sm:max-w-[38rem]"
      >
        <DialogTitle className="sr-only">{t("commandPalette")}</DialogTitle>
        <DialogDescription className="sr-only">{t("commandDescription")}</DialogDescription>
        <PaletteBody onDone={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}
