// Top command bar: brand and where you are on the left, the places of the app as one segmented
// control in the middle, and search (⌘K), backend status and the day/night switch on the right.

import { Link, useLocation } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Camera, KeyRound, LayoutGrid, Map, Megaphone, Moon, Search, Store, Sun } from "lucide-react";

import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";

import { BrandMark } from "./BrandMark";
import { MOD_KEY, useCommandPalette } from "./commandPalette";
import { projectIdFromPath } from "./paths";
import { useTheme } from "./theme";

const PAGE_TITLES: Record<string, string> = {
  "/projects/new": "New store",
  "/settings": "Model providers",
};

interface NavItem {
  to: string;
  params?: Record<string, string>;
  label: string;
  icon: typeof Store;
  active: boolean;
  disabled?: boolean;
}

function NavSegment({ items }: { items: NavItem[] }) {
  return (
    <nav aria-label="Main" className="glass col-span-2 row-start-2 flex items-center justify-self-center gap-0.5 rounded-2xl p-1 sm:col-span-1 sm:col-start-2 sm:row-start-1">
      {items.map(({ to, params, label, icon: Icon, active, disabled }) =>
        disabled ? (
          <span
            key={label}
            className="flex h-9 cursor-not-allowed items-center gap-2 rounded-xl px-3 text-sm text-muted-foreground/35"
            role="link"
            aria-label={label}
            aria-disabled="true"
            title="Open a store first"
          >
            <Icon className="size-[1.05rem]" aria-hidden />
            <span className="hidden lg:inline">{label}</span>
          </span>
        ) : (
          <Link
            key={label}
            to={to}
            params={params}
            aria-label={label}
            title={label}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex h-9 items-center gap-2 rounded-xl px-3 text-sm font-medium transition-[color,background-color,box-shadow] duration-200",
              active
                ? "bg-primary text-primary-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.3),0_8px_22px_-10px_var(--primary)]"
                : "text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground",
            )}
          >
            <Icon className="size-[1.05rem]" aria-hidden />
            <span className="hidden lg:inline">{label}</span>
          </Link>
        ),
      )}
    </nav>
  );
}

function BackendStatus() {
  const { isError, isSuccess } = useQuery({
    queryKey: queryKeys.health(),
    queryFn: ({ signal }) => api.getHealth(signal),
    refetchInterval: 15_000,
    retry: false,
  });
  const label = isError ? "Offline" : isSuccess ? "Live" : "…";
  return (
    <span
      className="hidden h-9 items-center gap-2 rounded-xl px-2.5 text-xs font-medium text-muted-foreground md:flex"
      title={isError ? "The backend is not reachable" : "Backend connected"}
    >
      <span
        className={cn(
          "size-2 rounded-full",
          isError ? "bg-negative" : isSuccess ? "animate-pulse-ring bg-volt" : "bg-muted-foreground/50",
        )}
        aria-hidden
      />
      <span className="num">{label}</span>
    </span>
  );
}

function ThemeSwitch() {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      className="glass relative flex h-9 w-[4.2rem] shrink-0 items-center rounded-full p-1"
      aria-label={dark ? "Switch to day theme" : "Switch to night theme"}
      title={dark ? "Day theme" : "Night theme"}
    >
      <Sun className="absolute left-2.5 size-3.5 text-muted-foreground" aria-hidden />
      <Moon className="absolute right-2.5 size-3.5 text-muted-foreground" aria-hidden />
      <span
        className={cn(
          "relative z-10 grid size-7 place-items-center rounded-full bg-primary text-primary-foreground shadow-[0_4px_14px_-4px_var(--primary)] transition-transform duration-300 ease-[cubic-bezier(0.3,1.4,0.5,1)]",
          dark ? "translate-x-[1.95rem]" : "translate-x-0",
        )}
        aria-hidden
      >
        {dark ? <Moon className="size-3.5" /> : <Sun className="size-3.5" />}
      </span>
    </button>
  );
}

export function CommandBar() {
  const { pathname } = useLocation();
  const pid = projectIdFromPath(pathname);
  const openPalette = useCommandPalette((s) => s.setOpen);

  const { data: project } = useQuery({
    queryKey: pid ? queryKeys.project(pid) : ["project", "disabled"],
    queryFn: ({ signal }) => api.getProject(pid!, signal),
    enabled: !!pid,
  });

  const sub = pathname.startsWith("/town/") ? "Neighborhood" : pathname.startsWith("/capture/") ? "Shelf capture" : pathname.startsWith("/marketing/") ? "Marketing studio" : null;
  const pageTitle = PAGE_TITLES[pathname];

  const items: NavItem[] = [
    { to: "/", label: "Stores", icon: LayoutGrid, active: pathname === "/" || pathname === "/projects/new" },
    { to: "/projects/$pid", params: { pid: pid ?? "" }, label: "Floor", icon: Store, active: pathname.startsWith("/projects/") && !!pid, disabled: !pid },
    { to: "/town/$pid", params: { pid: pid ?? "" }, label: "Area", icon: Map, active: pathname.startsWith("/town/"), disabled: !pid },
    { to: "/capture/$pid", params: { pid: pid ?? "" }, label: "Capture", icon: Camera, active: pathname.startsWith("/capture/"), disabled: !pid },
    { to: "/marketing/$pid", params: { pid: pid ?? "" }, label: "Market", icon: Megaphone, active: pathname.startsWith("/marketing/"), disabled: !pid },
    { to: "/settings", label: "Models", icon: KeyRound, active: pathname === "/settings" },
  ];

  return (
    <header className="relative z-30 grid shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 px-3 py-2 sm:h-[4.25rem] sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:gap-4 sm:px-4 sm:py-0 after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-[linear-gradient(90deg,transparent,var(--border)_20%,var(--border)_80%,transparent)]">
      <div className="flex min-w-0 items-center gap-3">
        <Link to="/" className="flex shrink-0 items-center gap-2.5 rounded-xl" aria-label="TwinStore home">
          <BrandMark />
          <span className="hidden font-display text-[1.08rem] tracking-[-0.045em] xl:block">
            <span className="aurora-text">twin</span>store
          </span>
        </Link>
        {(pid || pageTitle) && (
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-sm">
            <span className="h-5 w-px rotate-[18deg] bg-foreground/15" aria-hidden />
            {pid ? (
              <>
                <Link
                  to="/projects/$pid"
                  params={{ pid }}
                  className="truncate rounded-lg px-1.5 py-1 font-semibold tracking-[-0.02em] transition-colors hover:bg-foreground/[0.06]"
                >
                  {project?.metadata.name ?? "…"}
                </Link>
                {sub && (
                  <>
                    <span className="h-5 w-px rotate-[18deg] bg-foreground/15" aria-hidden />
                    <span className="truncate text-muted-foreground">{sub}</span>
                  </>
                )}
              </>
            ) : (
              <span className="truncate font-semibold tracking-[-0.02em]">{pageTitle}</span>
            )}
          </nav>
        )}
      </div>

      <NavSegment items={items} />

      <div className="col-start-2 row-start-1 flex items-center justify-end gap-2 sm:col-start-3">
        <button
          type="button"
          onClick={() => openPalette(true)}
          className="glass group flex h-9 min-w-0 items-center gap-2.5 rounded-xl pr-1.5 pl-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Search and jump (command palette)"
        >
          <Search className="size-4 shrink-0" aria-hidden />
          <span className="hidden truncate xl:inline">Jump to…</span>
          <kbd className="num hidden rounded-md border bg-foreground/[0.04] px-1.5 py-0.5 text-[0.7rem] text-muted-foreground sm:inline">
            {MOD_KEY} K
          </kbd>
        </button>
        <BackendStatus />
        <ThemeSwitch />
      </div>
    </header>
  );
}
