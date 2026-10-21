import { useState, type CSSProperties } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowRight, CloudSun, Eye, KeyRound, Map, Search, Sparkles, Wand2 } from "lucide-react";

import { MOD_KEY } from "@/app/commandPalette";
import { HeroStore } from "@/features/home/HeroStore";
import { NewStoreTile, StoreTile, StoreTileSkeleton } from "@/features/home/StoreTile";
import { Button } from "@/shared/components/ui/button";
import { useProjects } from "@/shared/queries/useProjects";

export const Route = createFileRoute("/")({
  component: HomePage,
});

const CAPABILITIES = [
  { icon: Eye, label: "Vision shoppers" },
  { icon: CloudSun, label: "19 situations" },
  { icon: Map, label: "Real neighborhoods" },
  { icon: Wand2, label: "Layout optimizer" },
];

function FloatingChip({ className, eyebrow, value, style }: { className: string; eyebrow: string; value: string; style?: CSSProperties }) {
  return (
    <div className={`glass absolute animate-float rounded-2xl px-4 py-3 ${className}`} style={style}>
      <div className="eyebrow">{eyebrow}</div>
      <div className="mt-0.5 font-display text-lg leading-none">{value}</div>
    </div>
  );
}

function HomePage() {
  const navigate = useNavigate();
  const { data: projects, isLoading, error, refetch } = useProjects();
  const [filter, setFilter] = useState("");
  const newStore = () => navigate({ to: "/projects/new" });

  const shown = (projects ?? []).filter((p) =>
    `${p.name} ${p.store_type} ${p.description}`.toLowerCase().includes(filter.trim().toLowerCase()),
  );

  return (
    <div className="flex-1 overflow-y-auto">
      <section className="relative">
        <div className="hero-glow pointer-events-none absolute inset-0 [mask-image:linear-gradient(to_bottom,black_55%,transparent)]" aria-hidden />
        <div className="relative mx-auto grid max-w-7xl items-center gap-10 px-6 pt-12 pb-14 lg:grid-cols-[1.1fr_1fr] lg:pt-14">
          <div className="max-w-[44rem]">
            <div className="glass inline-flex animate-rise items-center gap-2 rounded-full py-1 pr-3 pl-1 text-xs font-medium">
              <span className="rounded-full bg-primary px-2 py-0.5 font-mono text-[0.68rem] font-semibold text-primary-foreground">v0.3</span>
              <Sparkles className="size-3.5 text-heat-2" aria-hidden />
              Vision-language shoppers decide every move
            </div>
            <h1 className="mt-6 animate-rise font-display text-[clamp(2.6rem,4.5vw,4.7rem)] leading-[0.95] tracking-[-0.05em] [animation-delay:80ms]">
              Walk a thousand shoppers through your store
              <span className="mt-1 block font-accent text-[1.06em] leading-[1] tracking-[-0.015em]">
                <span className="aurora-text pr-2">before you move a shelf.</span>
              </span>
            </h1>
            <p className="mt-6 max-w-lg animate-rise text-lg leading-relaxed text-muted-foreground [animation-delay:160ms]">
              Draw the floor, set the day — weather, promotions, the shop next door — and synthetic shoppers show you
              where they walk, what they notice and what they buy.
            </p>
            <div className="mt-8 flex animate-rise flex-wrap items-center gap-3 [animation-delay:240ms]">
              <Button size="lg" className="h-12 gap-2 rounded-2xl px-6 text-base" onClick={newStore}>
                New store
                <ArrowRight className="size-4 transition-transform group-hover/button:translate-x-0.5" aria-hidden />
              </Button>
              <Button size="lg" variant="outline" className="h-12 gap-2 rounded-2xl px-5 text-base" onClick={() => navigate({ to: "/settings" })}>
                <KeyRound className="size-4" aria-hidden />
                Connect a model
              </Button>
              <span className="hidden items-center gap-1.5 pl-2 text-sm text-muted-foreground sm:flex">
                or press
                <kbd className="num rounded-md border bg-card/60 px-1.5 py-0.5 text-xs">{MOD_KEY} K</kbd>
              </span>
            </div>
            <div className="mt-10 flex animate-rise flex-wrap gap-2 [animation-delay:320ms]">
              {CAPABILITIES.map(({ icon: Icon, label }) => (
                <span key={label} className="inline-flex items-center gap-2 rounded-full border border-glass-border bg-card/40 px-3 py-1.5 text-sm text-muted-foreground backdrop-blur">
                  <Icon className="size-4 text-foreground/80" aria-hidden />
                  {label}
                </span>
              ))}
            </div>
          </div>

          <div className="relative animate-rise [animation-delay:200ms]">
            <div className="ring-aurora relative overflow-hidden rounded-[2rem] bg-card/40 p-4 shadow-[var(--shadow-lift)] backdrop-blur-xl">
              <div className="dot-grid absolute inset-0 opacity-70" aria-hidden />
              <div className="relative flex items-center justify-end px-2 pb-1">
                <span className="eyebrow flex items-center gap-1.5">
                  <span className="size-1.5 animate-pulse-ring rounded-full bg-volt" aria-hidden />
                  Live simulation
                </span>
              </div>
              <div className="relative aspect-[16/10] w-full">
                <HeroStore />
              </div>
            </div>
            <FloatingChip className="-top-7 -left-7 hidden md:block" eyebrow="Store formats" value="10 ready-made" />
            <FloatingChip className="-right-3 bottom-16 hidden md:block" eyebrow="Any vision model" value="Cloud or on-device" style={{ animationDelay: "1.4s" }} />
            <FloatingChip className="-bottom-6 left-10 hidden md:block" eyebrow="Paired A/B" value="With confidence intervals" style={{ animationDelay: "2.6s" }} />
          </div>
        </div>
      </section>

      <section className="relative mx-auto max-w-7xl px-6 pt-6 pb-16">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="eyebrow">Workspace</div>
            <h2 className="mt-1 font-display text-[2rem] leading-none">
              Your stores
              {projects && projects.length > 0 && <span className="num ml-3 align-middle text-base text-muted-foreground">{projects.length}</span>}
            </h2>
          </div>
          {projects && projects.length > 1 && (
            <label className="glass flex h-10 w-full max-w-xs items-center gap-2 rounded-xl px-3 text-sm sm:w-72">
              <Search className="size-4 text-muted-foreground" aria-hidden />
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter stores"
                className="w-full bg-transparent outline-none placeholder:text-muted-foreground"
                aria-label="Filter stores"
              />
            </label>
          )}
        </div>

        {error && (
          <div className="tone-bad mb-5 flex items-center justify-between gap-3 rounded-2xl border p-4 text-sm">
            {error instanceof Error ? error.message : "Could not load stores"}
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Try again
            </Button>
          </div>
        )}

        {isLoading ? (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => <StoreTileSkeleton key={i} />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {shown.map((p, i) => (
              <StoreTile key={p.project_id} index={i} project={p} onOpen={() => navigate({ to: "/projects/$pid", params: { pid: p.project_id } })} />
            ))}
            <NewStoreTile onClick={newStore} />
          </div>
        )}
      </section>
    </div>
  );
}
