import { createFileRoute } from "@tanstack/react-router";

import { OnlinePage } from "@/features/online/OnlinePage";

export const Route = createFileRoute("/online/$pid")({
  component: OnlineRoute,
});

function OnlineRoute() {
  const { pid } = Route.useParams();
  return <OnlinePage key={pid} projectId={pid} />;
}
