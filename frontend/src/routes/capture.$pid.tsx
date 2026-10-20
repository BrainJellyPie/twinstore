import { createFileRoute } from "@tanstack/react-router";

import { CapturePage } from "@/features/capture/CapturePage";

export const Route = createFileRoute("/capture/$pid")({
  component: CaptureRoute,
});

function CaptureRoute() {
  const { pid } = Route.useParams();
  return <CapturePage projectId={pid} />;
}
