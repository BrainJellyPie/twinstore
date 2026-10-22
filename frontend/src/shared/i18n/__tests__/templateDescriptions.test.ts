import { expect, it } from "vitest";
import { LOCALES } from "../messages";
import { templateDescriptionMessages } from "../templateDescriptionMessages";
import { templateDescription } from "../storeLabels";

it.each(LOCALES)("localizes every unchanged built-in description and leaves custom or newer descriptions untouched in $code", ({ code }) => {
  const column = LOCALES.findIndex(locale => locale.code === code);
  for (const [key, row] of Object.entries(templateDescriptionMessages)) {
    const id = key.slice("tplDesc_".length);
    expect(templateDescription(id, row[0], code), id).toBe(row[column]);
    expect(templateDescription(id, `${row[0]} Updated hours: 0–24.`, code), id).toBe(`${row[0]} Updated hours: 0–24.`);
    expect(templateDescription(id, "", code), id).toBe("");
  }
});
it.each(["unknown", "__proto__", "constructor", "toString", "", "urban_cvs ", "都市🛒"])("leaves unrecognized id %s and raw description text untouched", id => {
  const original = "<script>Tea & Café 茶</script> {count} \n 0–24 🛒";
  for (const { code } of LOCALES) expect(templateDescription(id, original, code)).toBe(original);
});
it("requires an exact source match rather than trimming, case-folding or Unicode-normalizing user data", () => {
  const original = templateDescriptionMessages.tplDesc_urban_cvs[0];
  for (const modified of [` ${original}`, `${original}\n`, original.toUpperCase(), `${original}\u200b`, "Café", "Cafe\u0301", "x".repeat(100_000)]) {
    expect(templateDescription("urban_cvs", modified, "fr")).toBe(modified);
  }
});
