// Display labels for persona quota values and report segment names. The values themselves are backend contract
// values (domain/persona.py: "10s"…"60s+", "Male"/"Female") and are sent unchanged; only how they read is translated.

import type { MessageKey } from "@/shared/i18n/messages";

type Translate = (key: MessageKey, values?: Record<string, string | number>) => string;

export const AGE_GROUPS = ["10s", "20s", "30s", "40s", "50s", "60s+"];
export const GENDERS = ["Female", "Male"];

const LABELS: Record<string, MessageKey> = {
  "10s": "studioAge10s", "20s": "studioAge20s", "30s": "studioAge30s", "40s": "studioAge40s", "50s": "studioAge50s",
  "60s+": "studioAge60s", Female: "studioFemale", Male: "studioMale",
};

/** An age group or gender as it reads in the selected language; unknown values are shown as they are. */
export function personaLabel(value: string, t: Translate): string {
  return Object.prototype.hasOwnProperty.call(LABELS, value) ? t(LABELS[value]!) : value;
}

/** Report segments: "age 20s" / "gender Female", or "age_group: 20s" / "gender: Female" from staff-script tests. */
export function segmentLabel(segment: string, t: Translate): string {
  const match = /^(age|age_group|gender):? (.+)$/.exec(segment);
  if (!match) return segment;
  const value = personaLabel(match[2]!, t);
  return match[1] === "gender" ? value : t("studioSegmentAge", { age: value });
}
