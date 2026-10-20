import { createFileRoute } from "@tanstack/react-router";
import { KeyRound } from "lucide-react";

import { ProvidersPanel } from "@/features/settings/ProvidersPanel";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <KeyRound className="size-5" aria-hidden /> Model providers
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Connect the language and vision models that drive synthetic shoppers. Keys are stored only on the machine
          running the Parastore backend (<code className="text-xs">.data/settings/providers.json</code>), never in run
          results, and are never sent back to the browser. Models of every ready provider appear in the run launcher,
          where several can be combined into an ensemble of consumers.
        </p>
        <div className="mt-6">
          <ProvidersPanel />
        </div>
      </div>
    </div>
  );
}
