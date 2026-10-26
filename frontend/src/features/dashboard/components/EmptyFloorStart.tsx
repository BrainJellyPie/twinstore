import { ArrowRight } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { useSimulationStore } from "@/stores/simulationStore";

/** The way from an empty floor to its first step: the side panel's floor configuration. */
export function EmptyFloorStart({ className }: { className?: string }) {
  const { t } = useI18n();
  const setActiveTab = useSimulationStore((s) => s.setActiveTab);
  return (
    <Button variant="outline" size="sm" className={className} onClick={() => setActiveTab("dashboard")}>
      {t("emptyFloorStart")} <ArrowRight aria-hidden />
    </Button>
  );
}
