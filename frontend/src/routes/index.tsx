import { type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Aperture, ArrowRight, CloudSun, Eye, KeyRound, Megaphone, MessagesSquare, Sparkles, Wand2 } from "lucide-react";

import { MOD_KEY } from "@/app/commandPalette";
import { HeroStore } from "@/features/home/HeroStore";
import { StoreGallery } from "@/features/home/StoreGallery";
import { Button } from "@/shared/components/ui/button";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { useProjects } from "@/shared/queries/useProjects";

export const Route = createFileRoute("/")({
  component: HomePage,
});

const CAPABILITIES = [
  { icon: Eye, label: "Vision shoppers" },
  { icon: CloudSun, label: "Situations" },
  { icon: Megaphone, label: "Marketing studio" },
  { icon: MessagesSquare, label: "Shopper interviews" },
  { icon: Aperture, label: "Photo mode" },
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
  const { data: projects, isLoading, isFetching, error, refetch } = useProjects();
  const newStore = () => navigate({ to: "/projects/new" });
  const templates = useQuery({ queryKey: ["store-templates"], queryFn: ({ signal }) => api.getStoreTemplates(signal), staleTime: Infinity });
  const scenarios = useQuery({ queryKey: queryKeys.scenarios(), queryFn: ({ signal }) => api.getScenarios(signal), staleTime: Infinity });
  const counted = (label: string) =>
    label === "Situations" && scenarios.data ? `${scenarios.data.length} situations` : label;

  return (
    <div className="flex-1 overflow-y-auto">
      <section className="relative">
        <div className="hero-glow pointer-events-none absolute inset-0 [mask-image:linear-gradient(to_bottom,black_55%,transparent)]" aria-hidden />
        <div className="relative mx-auto grid max-w-7xl items-center gap-10 px-6 pt-12 pb-14 lg:grid-cols-[1.1fr_1fr] lg:pt-14">
          <div className="max-w-[44rem]">
            <div className="glass inline-flex animate-rise items-center gap-2 rounded-full py-1 pr-3 pl-1 text-xs font-medium">
              <span className="rounded-full bg-primary px-2 py-0.5 font-mono text-[0.68rem] font-semibold text-primary-foreground">v0.4</span>
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
                  {counted(label)}
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
            <FloatingChip className="-top-7 -left-7 hidden md:block" eyebrow="Store formats" value={templates.data ? `${templates.data.length} ready-made` : "Ready-made"} />
            <FloatingChip className="-right-3 bottom-16 hidden md:block" eyebrow="Any vision model" value="Cloud or on-device" style={{ animationDelay: "1.4s" }} />
            <FloatingChip className="-bottom-6 left-10 hidden md:block" eyebrow="Paired A/B" value="Intervals and a report" style={{ animationDelay: "2.6s" }} />
          </div>
        </div>
      </section>

      <StoreGallery projects={projects} isLoading={isLoading} isFetching={isFetching} error={error}
        onRetry={() => { void refetch(); }} onCreate={newStore}
        onOpen={(pid) => { void navigate({ to: "/projects/$pid", params: { pid } }); }} />
    </div>
  );
}
