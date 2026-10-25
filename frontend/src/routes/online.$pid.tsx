import { createFileRoute, useRouterState } from "@tanstack/react-router";

import { OnlinePage } from "@/features/online/OnlinePage";

// Links from other tabs: `site` opens a store (with `compare`, its run form starts comparing it with that variant);
// `run` opens a run's report, and `shopper` with `variant` plays that shopper's visit to that store.
interface OnlineSearch { site?: string; compare?: string; run?: string; shopper?: string; variant?: number }

const text = (value: unknown) => (typeof value === "string" && value ? value : undefined);

export const Route = createFileRoute("/online/$pid")({
  validateSearch: (search: Record<string, unknown>): OnlineSearch => ({
    site: text(search.site), compare: text(search.compare), run: text(search.run), shopper: text(search.shopper),
    variant: typeof search.variant === "number" && Number.isInteger(search.variant) && search.variant >= 0 ? search.variant : undefined,
  }),
  component: OnlineRoute,
});

function OnlineRoute() {
  const { pid } = Route.useParams();
  const { site, compare, run, shopper, variant } = Route.useSearch();
  // Saving the current selection replaces this entry's URL, retaining its key.
  // Routed links get a new key, so their incoming selection still opens afresh.
  // Wait for the resolved location: a pending entry can still have the old route search.
  const entry = useRouterState({ select: (state) => (state.resolvedLocation ?? state.location).state.__TSR_key });
  return <OnlinePage key={JSON.stringify([pid, entry])} projectId={pid} initialSite={site}
    initialCompare={compare} initialRun={run} initialShopper={shopper ? { shopper, variant: variant ?? 0 } : undefined} />;
}
