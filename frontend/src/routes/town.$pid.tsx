import { createFileRoute } from "@tanstack/react-router";

import { TownPage } from "@/features/town/TownPage";

export const Route = createFileRoute("/town/$pid")({
  component: TownRoute,
});

function TownRoute() {
  const { pid } = Route.useParams();
  return <TownPage projectId={pid} />;
}
