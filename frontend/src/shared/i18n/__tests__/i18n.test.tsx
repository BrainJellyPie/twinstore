// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readLocale, resolveLocale, translate, useI18n, useLocale } from "../i18n";
import { LanguagePicker } from "../LanguagePicker";
import { LOCALES, messages, type Locale, type MessageKey } from "../messages";
import { storeTypeLabel } from "@/features/home/storeLabels";

beforeEach(() => { localStorage.clear(); useLocale.getState().setLocale("en"); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); useLocale.getState().setLocale("en"); localStorage.clear(); });

it.each([
  ["en-US", "en"], ["KO_kr", "ko"], ["zh-Hant-TW", "zh"], [" ja-JP ", "ja"],
  ["es-MX", "es"], ["fr-CA", "fr"], ["de-DE", null], ["constructor", null], ["__proto__", null], ["", null], [null, null], [undefined, null],
])("resolves supported language codes safely (%s)", (code, expected) => { expect(resolveLocale(code)).toBe(expected); });

it.each(LOCALES)("has complete $code translations with matching placeholders", ({ code }) => {
  for (const key of Object.keys(messages) as MessageKey[]) {
    const text = translate(code, key);
    expect(text.trim(), `${code}.${key}`).not.toBe("");
    expect([...text.matchAll(/\{\w+\}/g)].map((m) => m[0]).sort()).toEqual([...messages[key][0].matchAll(/\{\w+\}/g)].map((m) => m[0]).sort());
  }
});

it("prefers a saved selection to browser languages", () => {
  localStorage.setItem("twinstore.locale", "fr-CA");
  vi.spyOn(navigator, "languages", "get").mockReturnValue(["ko-KR"]);
  expect(readLocale()).toBe("fr");
});

it("uses the first supported browser language when saved data is invalid", () => {
  localStorage.setItem("twinstore.locale", "obsolete");
  vi.spyOn(navigator, "languages", "get").mockReturnValue(["de-DE", "ja-JP", "ko-KR"]);
  expect(readLocale()).toBe("ja");
});

it("falls back to English with no supported browser language", () => {
  localStorage.removeItem("twinstore.locale");
  vi.spyOn(navigator, "languages", "get").mockReturnValue(["de-DE"]);
  vi.spyOn(navigator, "language", "get").mockReturnValue("de-DE");
  expect(readLocale()).toBe("en");
});

it("can detect language without browser storage", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Unavailable"); });
  vi.spyOn(navigator, "languages", "get").mockReturnValue(["zh-CN"]);
  expect(readLocale()).toBe("zh");
});

function Preview() { const { t } = useI18n(); return <><LanguagePicker /><h1>{t("yourStores")}</h1></>; }
it.each(LOCALES)("switches $code without a reload and persists the choice", ({ code }) => {
  render(<Preview />);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: code } });
  expect(screen.getByRole("heading").textContent).toBe(translate(code, "yourStores"));
  expect(screen.getByRole("combobox").getAttribute("aria-label")).toBe(translate(code, "language"));
  expect(document.documentElement.lang).toBe(code);
  expect(localStorage.getItem("twinstore.locale")).toBe(code);
  expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe(code);
});

it("switches for this page even if persistence is blocked", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Blocked"); });
  render(<Preview />);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "ko" } });
  expect(screen.getByRole("heading").textContent).toBe("내 매장");
  expect(document.documentElement.lang).toBe("ko");
});

it("ignores unsupported stored or runtime values", () => {
  useLocale.getState().setLocale("invalid" as Locale);
  expect(useLocale.getState().locale).toBe("en");
  expect(document.documentElement.lang).toBe("en");
  expect(translate("invalid" as Locale, "newStore")).toBe("New store");
});

it.each(LOCALES)("formats counts and keeps custom names intact in $code", ({ code }) => {
  const count = new Intl.NumberFormat(code).format(10000);
  expect(translate(code, "filteredStores", { shown: 10000, total: 10000 })).toContain(count);
  expect(translate(code, "openStoreIn", { name: "A {name} <b>" })).toContain("A {name} <b>");
  expect(storeTypeLabel("cafe", code)).toBe(translate(code, "cafe"));
  expect(storeTypeLabel("pizza_shop", code)).toBe("Pizza shop");
  expect(storeTypeLabel("constructor", code)).toBe("Constructor");
  expect(storeTypeLabel("__proto__", code)).toBe("Proto");
});
