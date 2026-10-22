import { createFileRoute } from "@tanstack/react-router";
import { KeyRound } from "lucide-react";

import { LocalModelPanel } from "@/features/settings/LocalModelPanel";
import { ProvidersPanel } from "@/features/settings/ProvidersPanel";
import { useI18n } from "@/shared/i18n/i18n";
import { richText } from "@/shared/i18n/richText";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const { t } = useI18n();
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex items-start gap-4">
          <span className="ring-aurora grid size-12 shrink-0 place-items-center rounded-2xl bg-card/60">
            <KeyRound className="size-5" aria-hidden />
          </span>
          <div>
            <div className="eyebrow">{t("settingsEyebrow")}</div>
            <h1 className="font-display text-[2.2rem] leading-none">
              {t("modelProviders")} <span className="font-accent aurora-text pr-1">{t("settingsTagline")}</span>
            </h1>
          </div>
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          {richText(t("settingsIntro"), { path: <code className="text-xs">.data/settings/providers.json</code> })}
        </p>
        <div className="mt-6 space-y-8">
          <LocalModelPanel />
          <ProvidersPanel />
        </div>
      </div>
    </div>
  );
}
