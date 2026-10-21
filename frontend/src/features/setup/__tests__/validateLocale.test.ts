import { expect, it } from "vitest";
import { LOCALES } from "@/shared/i18n/messages";
import { translate } from "@/shared/i18n/translate";
import { DEFAULT_VALUES, validateStep1, validateStep2 } from "../validate";

const valid = { ...DEFAULT_VALUES, name: "Store", address: "12 Main Street", storeType: "convenience", customerProfile: "Local residents" };
const maximum = new File([new Uint8Array(10 * 1024 * 1024)], "customers.CSV");
const oversized = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "customers.csv");

it.each(LOCALES)("validates required fields and hours in $code", ({ code }) => {
  expect(validateStep1(DEFAULT_VALUES, code)).toEqual({ ok: false, errors: { name: translate(code, "nameRequired"), address: translate(code, "addressRequired"), storeType: translate(code, "storeTypeRequired") } });
  expect(validateStep1({ ...valid, openHour: 23, closeHour: 2 }, code)).toEqual({ ok: false, errors: { closeHour: translate(code, "hoursRangeError") } });
  expect(validateStep2(DEFAULT_VALUES, code)).toEqual({ ok: false, errors: { customerProfile: translate(code, "profileRequired") } });
});

it.each(LOCALES)("keeps file limits and uppercase extensions consistent in $code", ({ code }) => {
  expect(validateStep2({ ...valid, supplementalFile: maximum }, code)).toEqual({ ok: true });
  expect(validateStep2({ ...valid, supplementalFile: oversized }, code)).toEqual({ ok: false, errors: { supplementalFile: translate(code, "supplementalSizeError") } });
  expect(validateStep2({ ...valid, supplementalFile: new File(["data"], "customers.txt") }, code)).toEqual({ ok: false, errors: { supplementalFile: translate(code, "supplementalFormatError") } });
});

it("keeps the English default and treats whitespace-only fields as missing", () => {
  expect(validateStep1({ ...valid, name: "   " })).toEqual({ ok: false, errors: { name: "Store name is required" } });
  expect(validateStep2({ ...valid, customerProfile: "   " })).toEqual({ ok: false, errors: { customerProfile: "Tell us about your customers" } });
});
