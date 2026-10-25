import { createFileRoute } from "@tanstack/react-router";

import { OnlinePage } from "@/features/online/OnlinePage";

// `site` opens a store; with `compare`, its run form starts comparing it with that variant (links from other tabs).
interface OnlineSearch { site?: string; compare?: string }

export const Route = createFileRoute("/online/$pid")({
  validateSearch: (search: Record<string, unknown>): OnlineSearch => ({
    site: typeof search.site === "string" && search.site ? search.site : undefined,
    compare: typeof search.compare === "string" && search.compare ? search.compare : undefined,
  }),
  component: OnlineRoute,
});

function OnlineRoute() {
  const { pid } = Route.useParams();
  const { site, compare } = Route.useSearch();
  return <OnlinePage key={`${pid}:${site ?? ""}:${compare ?? ""}`} projectId={pid} initialSite={site} initialCompare={compare} />;
}
