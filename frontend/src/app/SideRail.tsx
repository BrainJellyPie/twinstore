// Left navigation rail: brand mark, the places of the app, and the day/night switch.
// The current place is marked by the heat-ramp bar — the app's signature color.

import { Link, useLocation } from "@tanstack/react-router";
import { KeyRound, LayoutGrid, Map, Moon, Store, Sun } from "lucide-react";

import { cn } from "@/shared/utils/cn";

import { useTheme } from "./theme";

function BrandMark() {
  return (
    <svg viewBox="0 0 40 40" className="size-9" aria-hidden>
      <defs>
        <linearGradient id="brand-heat" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--heat-1)" />
          <stop offset="0.55" stopColor="var(--heat-2)" />
          <stop offset="1" stopColor="var(--heat-3)" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#brand-heat)" />
      {/* An isometric shelf block with a shopper's path around it. */}
      <path d="M20 9 31 15.5v11L20 33 9 26.5v-11Z" fill="none" stroke="white" strokeWidth="2.2" strokeLinejoin="round" />
      <path d="M9 15.5 20 22l11-6.5M20 22v11" fill="none" stroke="white" strokeWidth="2.2" strokeLinejoin="round" opacity="0.85" />
      <circle cx="31.5" cy="31.5" r="3.2" fill="var(--tag)" stroke="white" strokeWidth="1.5" />
    </svg>
  );
}

interface Item {
  to: string;
  params?: Record<string, string>;
  label: string;
  icon: typeof Store;
  active: boolean;
  disabled?: boolean;
}

export function SideRail() {
  const { pathname } = useLocation();
  const { theme, toggle } = useTheme();
  const pid = pathname.match(/^\/(?:projects|town)\/([^/]+)/)?.[1];
  const inProject = !!pid && pid !== "new";

  const items: Item[] = [
    { to: "/", label: "Stores", icon: LayoutGrid, active: pathname === "/" || pathname === "/projects/new" },
    { to: "/projects/$pid", params: { pid: pid ?? "" }, label: "Floor", icon: Store, active: pathname.startsWith("/projects/") && inProject, disabled: !inProject },
    { to: "/town/$pid", params: { pid: pid ?? "" }, label: "Area", icon: Map, active: pathname.startsWith("/town/"), disabled: !inProject },
    { to: "/settings", label: "Models", icon: KeyRound, active: pathname === "/settings" },
  ];

  return (
    <nav aria-label="Main" className="flex w-[76px] shrink-0 flex-col items-center gap-1 border-r bg-rail py-3">
      <Link to="/" className="mb-4 rounded-xl focus-visible:outline-2" aria-label="Parastore home">
        <BrandMark />
      </Link>
      {items.map(({ to, params, label, icon: Icon, active, disabled }) =>
        disabled ? (
          <span key={label} className="flex w-16 flex-col items-center gap-1 rounded-xl py-2 text-[0.72rem] text-muted-foreground/40" title="Open a store first">
            <Icon className="size-5" aria-hidden />
            {label}
          </span>
        ) : (
          <Link
            key={label}
            to={to}
            params={params}
            className={cn(
              "relative flex w-16 flex-col items-center gap-1 rounded-xl py-2 text-[0.72rem] font-medium transition-colors",
              active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
            aria-current={active ? "page" : undefined}
          >
            {active && <span className="heat-gradient absolute -left-[6px] top-2 bottom-2 w-[4px] rounded-full" aria-hidden />}
            <Icon className="size-5" aria-hidden />
            {label}
          </Link>
        ),
      )}
      <div className="flex-1" />
      <button
        type="button"
        onClick={toggle}
        className="flex w-16 flex-col items-center gap-1 rounded-xl py-2 text-[0.72rem] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      >
        {theme === "dark" ? <Sun className="size-5" aria-hidden /> : <Moon className="size-5" aria-hidden />}
        {theme === "dark" ? "Day" : "Night"}
      </button>
    </nav>
  );
}
