import { createFileRoute } from "@tanstack/react-router";
import { KeyRound } from "lucide-react";

import { LocalModelPanel } from "@/features/settings/LocalModelPanel";
import { ProvidersPanel } from "@/features/settings/ProvidersPanel";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex items-start gap-4">
          <span className="ring-aurora grid size-12 shrink-0 place-items-center rounded-2xl bg-card/60">
            <KeyRound className="size-5" aria-hidden />
          </span>
          <div>
            <div className="eyebrow">Settings</div>
            <h1 className="font-display text-[2.2rem] leading-none">
              Model providers <span className="font-accent aurora-text pr-1">— the minds behind your shoppers</span>
            </h1>
          </div>
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          Connect the language and vision models that drive synthetic shoppers. Keys are stored only on the machine
          running the TwinStore backend (<code className="text-xs">.data/settings/providers.json</code>), never in run
          results, and are never sent back to the browser. Models of every ready provider appear in the run launcher,
          where several can be combined into an ensemble of consumers.
        </p>
        <div className="mt-6 space-y-8">
          <LocalModelPanel />
          <ProvidersPanel />
        </div>
      </div>
    </div>
  );
}
