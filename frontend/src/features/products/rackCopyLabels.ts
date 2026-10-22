import type { RackCopyChoice } from "@/shared/api/rackCopy";
import { LOCALES, type Locale, type MessageKey } from "@/shared/i18n/messages";
import { translate } from "@/shared/i18n/translate";

const reasons = new Map<string, MessageKey>([
  ["choose_stocked", "copyChooseSource"], ["source_inaccessible", "copyReasonBlockedSource"],
  ["source_invalid_products", "copyReasonInvalidSource"], ["source_rack", "copyReasonSource"],
  ["occupied", "copyReasonOccupied"], ["fixture_mismatch", "copyReasonShape"],
  ["target_inaccessible", "copyReasonBlockedTarget"],
]);
// Older API responses carry the same English explanation but no code.
const legacyReasons = new Map([...reasons.values()].map(key => [translate("en", key), key]));
export function rackCopyReason(rack: RackCopyChoice, locale: Locale): string | null {
  const key = reasons.get(rack.reason_code ?? "") ?? legacyReasons.get(rack.reason ?? "");
  return key ? translate(locale, key) : rack.reason;
}
const fixtures = new Map<string, MessageKey>([["shelf", "fixtureShelf"], ["fridge", "fixtureFridge"]]);
const faces = new Map<string, MessageKey>([["N", "fixtureNorth"], ["S", "fixtureSouth"], ["E", "fixtureEast"], ["W", "fixtureWest"]]);
export function fixtureLabel(type: string, locale: Locale): string {
  const key = fixtures.get(type); return key ? translate(locale, key) : type;
}
export function faceLabel(face: string, locale: Locale): string {
  const key = faces.get(face); return key ? translate(locale, key) : face;
}
export function fixtureSearchLabels(type: string): string {
  return LOCALES.map(locale => fixtureLabel(type, locale.code)).join(" ");
}
