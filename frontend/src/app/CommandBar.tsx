// Top command bar: brand and where you are on the left, the places of the app as one segmented
// control in the middle, and search (⌘K), backend status, the day/night switch and, under the launcher,
// Quit on the right.

import { useEffect, useState } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Camera, Globe2, KeyRound, LayoutGrid, Map, Megaphone, Moon, Search, Store, Sun } from "lucide-react";

import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { useProjects } from "@/shared/queries/useProjects";
import { cn } from "@/shared/utils/cn";

import { useI18n } from "@/shared/i18n/i18n";
import { LanguagePicker } from "@/shared/i18n/LanguagePicker";
import type { MessageKey } from "@/shared/i18n/messages";

import { BrandMark } from "./BrandMark";
import { MOD_KEY, useCommandPalette } from "./commandPalette";
import { LAST_STORE, projectIdFromPath } from "./paths";
import { QuitButton } from "./QuitTwinStore";
import { useTheme } from "./theme";

const PAGE_TITLES: Record<string, MessageKey> = {
  "/projects/new": "newStore",
  "/settings": "modelProviders",
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
  const { t } = useI18n();
  return (
    <nav aria-label={t("main")} className="glass col-span-2 row-start-2 flex items-center justify-self-center gap-0.5 rounded-2xl p-1 lg:col-span-1 lg:col-start-2 lg:row-start-1">
      {items.map(({ to, params, label, icon: Icon, active, disabled }) =>
        disabled ? (
          <span
            key={label}
            className="flex h-11 cursor-not-allowed flex-col items-center justify-center gap-1 rounded-xl px-2 text-sm text-muted-foreground/45 sm:h-9 sm:flex-row sm:gap-2 sm:px-3"
            role="link"
            aria-label={label}
            aria-disabled="true"
            title={t("openStoreFirst")}
          >
            <Icon className="size-[1.05rem]" aria-hidden />
            <span className="text-[0.68rem] leading-none whitespace-nowrap sm:hidden sm:text-sm sm:leading-normal min-[52rem]:inline lg:hidden xl:inline">{label}</span>
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
              "relative flex h-11 flex-col items-center justify-center gap-1 rounded-xl px-2 text-sm font-medium transition-[color,background-color,box-shadow] duration-200 sm:h-9 sm:flex-row sm:gap-2 sm:px-3",
              active
                ? "bg-primary text-primary-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.3),0_8px_22px_-10px_var(--primary)]"
                : "text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground",
            )}
          >
            <Icon className="size-[1.05rem]" aria-hidden />
            {/* Where the tabs share the top row with the store name (lg) only the current tab is named. */}
            <span className={cn("text-[0.68rem] leading-none whitespace-nowrap sm:text-sm sm:leading-normal", !active && "sm:hidden min-[52rem]:inline lg:hidden xl:inline")}>{label}</span>
          </Link>
        ),
      )}
    </nav>
  );
}

function BackendStatus() {
  const { t } = useI18n();
  const { isError, isSuccess } = useQuery({
    queryKey: queryKeys.health(),
    queryFn: ({ signal }) => api.getHealth(signal),
    refetchInterval: 15_000,
    retry: false,
  });
  const label = isError ? t("offline") : isSuccess ? t("live") : "…";
  return (
    <span
      className="hidden h-9 items-center gap-2 rounded-xl px-2.5 text-xs font-medium text-muted-foreground md:flex"
      title={isError ? t("backendOffline") : t("backendOnline")}
    >
      <span
        className={cn(
          "size-2 rounded-full",
          isError ? "bg-negative" : isSuccess ? "animate-pulse-ring bg-volt" : "bg-muted-foreground/50",
        )}
        aria-hidden
      />
      <span className="num sr-only 2xl:not-sr-only">{label}</span>
    </span>
  );
}

function ThemeSwitch() {
  const { t } = useI18n();
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      className="glass relative flex h-9 w-[4.2rem] shrink-0 items-center rounded-full p-1"
      aria-label={dark ? t("switchDay") : t("switchNight")}
      title={dark ? t("dayTheme") : t("nightTheme")}
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
  const { t } = useI18n();
  const { pathname } = useLocation();
  const pid = projectIdFromPath(pathname);
  const openPalette = useCommandPalette((s) => s.setOpen);
  // Off a store's pages (home, settings), the store tabs open the store used last, or the only one.
  const { data: projects } = useProjects();
  const [remembered, setRemembered] = useState<string | null>(() => {
    try { return localStorage.getItem(LAST_STORE); } catch { return null; }  // storage unavailable: nothing remembered
  });
  useEffect(() => {
    if (!pid) return;
    setRemembered(pid);
    try { localStorage.setItem(LAST_STORE, pid); } catch { /* storage unavailable: kept for this visit only */ }
  }, [pid]);
  const storeId = pid ?? (projects?.some((p) => p.project_id === remembered) ? remembered
    : projects?.length === 1 ? projects[0]!.project_id : null);

  const { data: project, isError: projectMissing } = useQuery({
    queryKey: pid ? queryKeys.project(pid) : ["project", "disabled"],
    queryFn: ({ signal }) => api.getProject(pid!, signal),
    enabled: !!pid,
  });

  const sub = pathname.startsWith("/town/") ? t("neighborhood") : pathname.startsWith("/capture/") ? t("shelfCapture") : pathname.startsWith("/marketing/") ? t("marketingStudio") : pathname.startsWith("/online/") ? t("onlineStores") : null;
  const pageKey = PAGE_TITLES[pathname];
  const pageTitle = pageKey ? t(pageKey) : undefined;

  const items: NavItem[] = [
    { to: "/", label: t("stores"), icon: LayoutGrid, active: pathname === "/" || pathname === "/projects/new" },
    { to: "/projects/$pid", params: { pid: storeId ?? "" }, label: t("floor"), icon: Store, active: pathname.startsWith("/projects/") && !!pid, disabled: !storeId },
    { to: "/town/$pid", params: { pid: storeId ?? "" }, label: t("area"), icon: Map, active: pathname.startsWith("/town/"), disabled: !storeId },
    { to: "/capture/$pid", params: { pid: storeId ?? "" }, label: t("capture"), icon: Camera, active: pathname.startsWith("/capture/"), disabled: !storeId },
    { to: "/marketing/$pid", params: { pid: storeId ?? "" }, label: t("market"), icon: Megaphone, active: pathname.startsWith("/marketing/"), disabled: !storeId },
    { to: "/online/$pid", params: { pid: storeId ?? "" }, label: t("online"), icon: Globe2, active: pathname.startsWith("/online/"), disabled: !storeId },
    { to: "/settings", label: t("models"), icon: KeyRound, active: pathname === "/settings" },
  ];

  return (
    <header className="relative z-30 grid shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 px-3 py-2 sm:px-4 lg:h-[4.25rem] lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:gap-4 lg:py-0 after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-[linear-gradient(90deg,transparent,var(--border)_20%,var(--border)_80%,transparent)]">
      <div className="flex min-w-0 items-center gap-3">
        <Link to="/" className="flex shrink-0 items-center gap-2.5 rounded-xl" aria-label={t("home")}>
          <BrandMark />
          {/* With a breadcrumb the wordmark waits for a wide screen, so the store and page names fit. */}
          <span className={cn("hidden font-display text-[1.08rem] tracking-[-0.045em]", pid || pageTitle ? "2xl:block" : "xl:block")}>
            <span className="aurora-text">twin</span>store
          </span>
        </Link>
        {((pid && !projectMissing) || pageTitle) && (
          <nav aria-label={t("breadcrumb")} className="flex min-w-0 items-center gap-2 text-sm">
            <span className="h-5 w-px rotate-[18deg] bg-foreground/15" aria-hidden />
            {pid ? (
              <>
                <Link
                  to="/projects/$pid"
                  params={{ pid }}
                  className="truncate rounded-lg px-1.5 py-1 font-semibold tracking-[-0.02em] transition-colors hover:bg-foreground/[0.06]"
                  title={project?.metadata.name}
                >
                  {project?.metadata.name ?? "…"}
                </Link>
                {/* The page name repeats the highlighted tab, so it waits for a wide screen and the store name fits. */}
                {sub && (
                  <span className="hidden min-w-0 items-center gap-2 2xl:flex">
                    <span className="h-5 w-px shrink-0 rotate-[18deg] bg-foreground/15" aria-hidden />
                    <span className="truncate text-muted-foreground">{sub}</span>
                  </span>
                )}
              </>
            ) : (
              <span className="truncate font-semibold tracking-[-0.02em]">{pageTitle}</span>
            )}
          </nav>
        )}
      </div>

      <NavSegment items={items} />

      <div className="col-start-2 row-start-1 flex items-center justify-end gap-2 lg:col-start-3">
        <button
          type="button"
          onClick={() => openPalette(true)}
          className="glass group flex h-9 min-w-0 items-center gap-2.5 rounded-xl pr-1.5 pl-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
          aria-label={t("searchCommands")}
        >
          <Search className="size-4 shrink-0" aria-hidden />
          <span className="hidden truncate 2xl:inline">{t("jumpTo")}</span>
          <kbd className="num hidden rounded-md border bg-foreground/[0.04] px-1.5 py-0.5 text-[0.7rem] text-muted-foreground sm:inline">
            {MOD_KEY} K
          </kbd>
        </button>
        <BackendStatus />
        <LanguagePicker />
        <ThemeSwitch />
        <QuitButton />
      </div>
    </header>
  );
}
