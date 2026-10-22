import type { MessageKey } from "@/shared/i18n/messages";

/** Recognition stages reported by the capture pipeline, with their display labels. */
export const STAGES: Record<string, MessageKey> = {
  queued: "capStageQueued", detecting: "capStageDetecting", grouping: "capStageGrouping",
  reading: "capStageReading", planogram: "capStagePlanogram", done: "capStageDone",
};
