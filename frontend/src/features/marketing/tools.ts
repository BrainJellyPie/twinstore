import { ClipboardList, FlaskConical, Grid3x3, Images, MessagesSquare, Rows3 } from "lucide-react";

import type { MessageKey } from "@/shared/i18n/messages";

export type MarketingTool = "ab" | "shelf" | "survey" | "conjoint" | "pitch" | "pilot" | "products" | "inventory" | "prices" | "protocols" | "priceChecks";

/** The studio's tools, in their tab order (also listed in the command palette). */
export const MARKETING_TOOLS: { id: MarketingTool; label: MessageKey; icon: typeof FlaskConical; blurb: MessageKey }[] = [
  { id: "ab", label: "mkTabAb", icon: FlaskConical, blurb: "mkTabAbBlurb" },
  { id: "shelf", label: "mkTabShelf", icon: Rows3, blurb: "mkTabShelfBlurb" },
  { id: "survey", label: "mkTabSurvey", icon: ClipboardList, blurb: "mkTabSurveyBlurb" },
  { id: "conjoint", label: "mkTabConjoint", icon: Grid3x3, blurb: "mkTabConjointBlurb" },
  { id: "pitch", label: "mkTabPitch", icon: MessagesSquare, blurb: "mkTabPitchBlurb" },
  { id: "pilot", label: "mkTabPilot", icon: ClipboardList, blurb: "mkTabPilotBlurb" },
  { id: "protocols", label: "mkTabProtocols", icon: ClipboardList, blurb: "mkTabProtocolsBlurb" },
  { id: "priceChecks", label: "mkTabPriceChecks", icon: ClipboardList, blurb: "mkTabPriceChecksBlurb" },
  { id: "prices", label: "mkTabPrices", icon: ClipboardList, blurb: "mkTabPricesBlurb" },
  { id: "inventory", label: "mkTabInventory", icon: ClipboardList, blurb: "mkTabInventoryBlurb" },
  { id: "products", label: "mkTabProducts", icon: Images, blurb: "mkTabProductsBlurb" },
];
