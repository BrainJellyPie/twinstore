// ⌘K / Ctrl+K (or "/") command palette: jump to any store or page, or flip the theme, from the
// keyboard. Arrow keys move, Enter runs, Esc closes.

import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";
import {
  ArrowRight,
  Camera,
  CornerDownLeft,
  KeyRound,
  LayoutGrid,
  Map,
  Moon,
  Plus,
  Search,
  Store,
  Sun,
} from "lucide-react";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import { useProjects } from "@/shared/queries/useProjects";
import { cn } from "@/shared/utils/cn";

import { useCommandPalette } from "./commandPalette";
import { projectIdFromPath } from "./paths";
import { useTheme } from "./theme";

interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: typeof Store;
  run: () => void;
}

function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

function matches(command: Command, query: string): boolean {
  const hay = `${command.label} ${command.hint ?? ""} ${command.group}`.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((token) => hay.includes(token));
}

function PaletteBody({ onDone }: { onDone: () => void }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const pid = projectIdFromPath(pathname);
  const { data: projects } = useProjects();
  const { theme, setTheme } = useTheme();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const itemRefs = useRef(new globalThis.Map<number, HTMLButtonElement>());

  const commands = useMemo<Command[]>(() => {
    const go = (to: string, params?: Record<string, string>) => () => navigate({ to, params });
    const list: Command[] = [];
    if (pid) {
      list.push(
        { id: "floor", group: "This store", label: "Floor & simulation", hint: "3D store, runs, results", icon: Store, run: go("/projects/$pid", { pid }) },
        { id: "area", group: "This store", label: "Neighborhood", hint: "demand, rivals, synergy", icon: Map, run: go("/town/$pid", { pid }) },
        { id: "capture", group: "This store", label: "Shelf capture", hint: "photo → planogram", icon: Camera, run: go("/capture/$pid", { pid }) },
      );
    }
    list.push(
      { id: "home", group: "Go to", label: "All stores", hint: "home", icon: LayoutGrid, run: go("/") },
      { id: "new", group: "Go to", label: "New store", hint: "create, wizard", icon: Plus, run: go("/projects/new") },
      { id: "models", group: "Go to", label: "Model providers", hint: "API keys, settings, vision", icon: KeyRound, run: go("/settings") },
    );
    for (const p of projects ?? []) {
      list.push({
        id: `store-${p.project_id}`,
        group: "Stores",
        label: p.name || "Untitled store",
        hint: p.store_type,
        icon: Store,
        run: go("/projects/$pid", { pid: p.project_id }),
      });
    }
    list.push(
      theme === "dark"
        ? { id: "theme", group: "Appearance", label: "Switch to day theme", hint: "light", icon: Sun, run: () => setTheme("light") }
        : { id: "theme", group: "Appearance", label: "Switch to night theme", hint: "dark", icon: Moon, run: () => setTheme("dark") },
    );
    return list;
  }, [navigate, pid, projects, theme, setTheme]);

  const visible = useMemo(() => commands.filter((c) => matches(c, query)), [commands, query]);
  const current = Math.min(active, Math.max(visible.length - 1, 0));

  useEffect(() => {
    itemRefs.current.get(current)?.scrollIntoView({ block: "nearest" });
  }, [current]);

  const run = (command: Command | undefined) => {
    if (!command) return;
    onDone();
    command.run();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
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
    <div onKeyDown={onKeyDown}>
      <div className="flex items-center gap-3 border-b px-5">
        <Search className="size-5 shrink-0 text-muted-foreground" aria-hidden />
        <input
          autoFocus
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          placeholder="Jump to a store, page or action…"
          className="h-16 w-full bg-transparent text-lg tracking-[-0.01em] outline-none placeholder:text-muted-foreground/70"
          aria-label="Command"
          role="combobox"
          aria-expanded
          aria-controls="command-list"
          aria-activedescendant={visible[current] ? `cmd-${visible[current].id}` : undefined}
        />
        <kbd className="num rounded-md border px-1.5 py-0.5 text-[0.7rem] text-muted-foreground">esc</kbd>
      </div>
      <div id="command-list" role="listbox" className="max-h-[min(26rem,60vh)] overflow-y-auto p-2">
        {visible.length === 0 && (
          <p className="px-3 py-10 text-center text-sm text-muted-foreground">Nothing matches “{query}”.</p>
        )}
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
                  <Icon className="size-4" aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[0.95rem] font-medium">{c.label}</span>
                  {c.hint && <span className="block truncate text-xs text-muted-foreground">{c.hint}</span>}
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
      <div className="flex items-center gap-4 border-t px-5 py-2.5 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <kbd className="num rounded border px-1">↑</kbd>
          <kbd className="num rounded border px-1">↓</kbd> move
        </span>
        <span className="flex items-center gap-1.5">
          <kbd className="num rounded border px-1">↵</kbd> open
        </span>
        <span className="ml-auto aurora-text font-medium">parastore</span>
      </div>
    </div>
  );
}

export function CommandPalette() {
  const open = useCommandPalette((s) => s.open);
  const setOpen = useCommandPalette((s) => s.setOpen);
  const toggle = useCommandPalette((s) => s.toggle);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
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
        className="ring-aurora top-[14vh] max-w-[calc(100%-2rem)] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-[38rem]"
      >
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">Search stores, pages and actions</DialogDescription>
        <PaletteBody onDone={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}
