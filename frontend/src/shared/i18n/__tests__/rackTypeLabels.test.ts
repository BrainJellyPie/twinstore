import { expect, it } from "vitest";
import { translate } from "../i18n";
import { rackTypeLabel } from "../rackTypeLabels";

it("reads rack types in the selected language and keeps unknown types as they are", () => {
  expect(rackTypeLabel("entrance", (key) => translate("ko", key))).toBe("입구");
  expect(rackTypeLabel("fridge", (key) => translate("en", key))).toBe("fridge");
  expect(rackTypeLabel("kiosk", (key) => translate("ko", key))).toBe("kiosk");
});
