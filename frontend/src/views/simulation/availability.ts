import { Package, Users, Loader2, DoorOpen, DoorClosed, ScanLine, type LucideIcon } from "lucide-react";
import type { Readiness, ReadinessReason } from "@/shared/types/domain";
import { translate } from "@/shared/i18n/translate";
import type { Locale, MessageKey } from "@/shared/i18n/messages";

export interface Availability {
  canSimulate: boolean;
  reasons: ReadinessReason[];
}

export function computeSimulationAvailability(readiness: Readiness | null): Availability {
  if (!readiness) return { canSimulate: false, reasons: [] };
  return { canSimulate: readiness.ready, reasons: readiness.reasons };
}

const REASON_KEYS: Record<ReadinessReason, MessageKey> = {
  no_personas: "readinessNoPersonas",
  no_items: "readinessNoItems",
  no_layout: "readinessNoLayout",
  layout_pending: "readinessLayoutPending",
  personas_pending: "readinessPersonasPending",
  no_entrance: "readinessNoEntrance",
  no_exit: "readinessNoExit",
  no_counter: "readinessNoCounter",
};

export function reasonLabel(reason: ReadinessReason, locale: Locale): string {
  return translate(locale, REASON_KEYS[reason]);
}

export function reasonIcon(reason: ReadinessReason): LucideIcon {
  switch (reason) {
    case "no_personas":
    case "personas_pending":
      return Users;
    case "no_items":
      return Package;
    case "no_layout":
    case "layout_pending":
      return Loader2;
    case "no_entrance":
      return DoorOpen;
    case "no_exit":
      return DoorClosed;
    case "no_counter":
      return ScanLine;
  }
}
