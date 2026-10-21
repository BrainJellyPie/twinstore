import { createFileRoute } from "@tanstack/react-router";

import { MarketingPage } from "@/features/marketing/MarketingPage";

export const Route = createFileRoute("/marketing/$pid")({
  component: MarketingRoute,
});

function MarketingRoute() {
  const { pid } = Route.useParams();
  return <MarketingPage key={pid} projectId={pid} />;
}
