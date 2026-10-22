// Display labels for persona age groups and genders, and for report segment names. The values themselves are backend
// contract values (domain/persona.py: "10s"…"60s+", "Male"/"Female") and are sent unchanged; only how they read is
// translated.

import type { MessageKey } from "./messages";

type Translate = (key: MessageKey, values?: Record<string, string | number>) => string;

export const AGE_GROUPS = ["10s", "20s", "30s", "40s", "50s", "60s+"];
export const GENDERS = ["Female", "Male"];

const LABELS: Record<string, MessageKey> = {
  "10s": "studioAge10s", "20s": "studioAge20s", "30s": "studioAge30s", "40s": "studioAge40s", "50s": "studioAge50s",
  "60s+": "studioAge60s", Female: "studioFemale", Male: "studioMale",
};

const BADGES: Record<string, MessageKey> = {
  "10s": "studioAgeBadge10s", "20s": "studioAgeBadge20s", "30s": "studioAgeBadge30s", "40s": "studioAgeBadge40s",
  "50s": "studioAgeBadge50s", "60s+": "studioAgeBadge60s",
};

const has = (table: Record<string, MessageKey>, value: string) => Object.prototype.hasOwnProperty.call(table, value);

/** An age group or gender as it reads in the selected language; unknown values are shown as they are. */
export function personaLabel(value: string, t: Translate): string {
  return has(LABELS, value) ? t(LABELS[value]!) : value;
}

/** The short age group for a small badge ("40대", "40–49"); unknown values are shown as they are. */
export function ageBadge(value: string, t: Translate): string {
  return has(BADGES, value) ? t(BADGES[value]!) : value;
}

/** Report segments: "age 20s" / "gender Female", or "age_group: 20s" / "gender: Female" from staff-script tests. */
export function segmentLabel(segment: string, t: Translate): string {
  const match = /^(age|age_group|gender):? (.+)$/.exec(segment);
  if (!match) return segment;
  const value = personaLabel(match[2]!, t);
  return match[1] === "gender" ? value : t("studioSegmentAge", { age: value });
}
