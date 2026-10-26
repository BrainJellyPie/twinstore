import { createFileRoute, useRouterState } from "@tanstack/react-router";

import { MarketingPage } from "@/features/marketing/MarketingPage";
import { MARKETING_TOOLS, type MarketingTool } from "@/features/marketing/tools";

// Links from elsewhere (the command palette): `tool` opens the studio on that tool.
interface MarketingSearch { tool?: MarketingTool }

export const Route = createFileRoute("/marketing/$pid")({
  validateSearch: (search: Record<string, unknown>): MarketingSearch => ({
    tool: MARKETING_TOOLS.find((item) => item.id === search.tool)?.id,
  }),
  component: MarketingRoute,
});

function MarketingRoute() {
  const { pid } = Route.useParams();
  const { tool } = Route.useSearch();
  // A routed link gets a new entry key, so a tool chosen while the studio is open still opens.
  const entry = useRouterState({ select: (state) => (state.resolvedLocation ?? state.location).state.__TSR_key });
  return <MarketingPage key={JSON.stringify([pid, tool ? entry : null])} projectId={pid} initialTool={tool} />;
}
