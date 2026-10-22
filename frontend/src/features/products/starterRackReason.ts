import type { StarterRack } from "@/shared/api/starterFill";
import type { Locale, MessageKey } from "@/shared/i18n/messages";
import { translate } from "@/shared/i18n/translate";

const reasons = new Map<string, MessageKey>([
  ["occupied", "copyReasonOccupied"], ["no_accessible_face", "starterNoFace"],
]);
const legacyReasons = new Map([...reasons.values()].map(key => [translate("en", key), key]));
export function starterRackReason(rack: StarterRack, locale: Locale): string | null {
  const key = reasons.get(rack.reason_code ?? "") ?? legacyReasons.get(rack.reason ?? "");
  return key ? translate(locale, key) : rack.reason;
}
