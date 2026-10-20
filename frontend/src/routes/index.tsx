import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { KeyRound, Plus } from "lucide-react";

import { HeroStore } from "@/features/home/HeroStore";
import { StoreTile, StoreTileSkeleton } from "@/features/home/StoreTile";
import { Button } from "@/shared/components/ui/button";
import { useProjects } from "@/shared/queries/useProjects";

export const Route = createFileRoute("/")({
  component: HomePage,
});

function HomePage() {
  const navigate = useNavigate();
  const { data: projects, isLoading, error, refetch } = useProjects();
  const newStore = () => navigate({ to: "/projects/new" });

  return (
    <div className="flex-1 overflow-y-auto">
      <section className="relative overflow-hidden border-b">
        <div className="hero-glow pointer-events-none absolute inset-0" aria-hidden />
        <div className="relative mx-auto grid max-w-6xl items-center gap-6 px-6 py-10 md:grid-cols-[1fr_1.15fr] md:py-14">
          <div className="max-w-xl">
            <h1 className="font-display text-[clamp(2.4rem,5vw,4.1rem)] leading-[0.98] font-bold tracking-[-0.035em]">
              Walk a thousand shoppers through your store before you move a shelf.
            </h1>
            <p className="mt-5 max-w-md text-lg leading-relaxed text-muted-foreground">
              Draw the floor, set the day — weather, promotions, the shop next door — and synthetic shoppers show
              you where they walk, what they notice and what they buy.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Button size="lg" className="h-11 gap-2 rounded-xl px-5 text-base" onClick={newStore}>
                <Plus className="size-4" aria-hidden />
                New store
              </Button>
              <Button size="lg" variant="outline" className="h-11 gap-2 rounded-xl px-5 text-base" onClick={() => navigate({ to: "/settings" })}>
                <KeyRound className="size-4" aria-hidden />
                Connect a model
              </Button>
            </div>
          </div>
          <div className="aspect-[16/10] w-full">
            <HeroStore />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-5 flex items-end justify-between gap-4">
          <h2 className="font-display text-2xl font-semibold tracking-tight">Your stores</h2>
          {projects && projects.length > 0 && (
            <span className="text-sm text-muted-foreground">
              {projects.length} {projects.length === 1 ? "store" : "stores"}
            </span>
          )}
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            {error instanceof Error ? error.message : "Could not load stores"}
            <button type="button" onClick={() => refetch()} className="ml-2 font-medium underline">
              Try again
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => <StoreTileSkeleton key={i} />)}
          </div>
        ) : !projects || projects.length === 0 ? (
          <button
            type="button"
            onClick={newStore}
            className="flex w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed py-14 text-center transition-colors hover:border-primary hover:bg-primary/5"
          >
            <span className="font-display text-xl font-semibold">Start with your first store</span>
            <span className="text-muted-foreground">Pick a format — convenience store, station kiosk, drugstore — and it lays out the floor for you.</span>
          </button>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <StoreTile key={p.project_id} project={p} onOpen={() => navigate({ to: "/projects/$pid", params: { pid: p.project_id } })} />
            ))}
            <button
              type="button"
              onClick={newStore}
              className="flex min-h-44 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
            >
              <Plus className="size-6" aria-hidden />
              <span className="font-medium">New store</span>
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
