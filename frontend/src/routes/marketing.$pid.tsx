import { useCallback } from "react";
import { createFileRoute } from "@tanstack/react-router";

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
  const navigate = Route.useNavigate();
  const selectTool = useCallback((next: MarketingTool) => {
    void navigate({ search: { tool: next }, replace: true });
  }, [navigate]);
  return <MarketingPage key={pid} projectId={pid} tool={tool ?? "ab"} onToolChange={selectTool} />;
}
