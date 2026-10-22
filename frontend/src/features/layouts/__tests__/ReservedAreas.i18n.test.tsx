// @vitest-environment jsdom
import { useState } from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES, type MessageKey } from "@/shared/i18n/messages";
import type { ReservedArea } from "@/shared/api/client";
import { ReservedAreasEditor } from "../components/ReservedAreasEditor";

const original = { label: "茶 & <Books> 🛒 {name}", x: 1, y: 1, width: 2, height: 3 };
function Form() {
  const [areas, setAreas] = useState<ReservedArea[]>([original]);
  return <><ReservedAreasEditor areas={areas} onChange={setAreas} grid={[12, 10]} /><output data-testid="areas">{JSON.stringify(areas)}</output></>;
}
const t = (key: MessageKey, values?: Record<string, string | number>) => translate(useLocale.getState().locale, key, values);
const areas = (): ReservedArea[] => JSON.parse(screen.getByTestId("areas").textContent!);
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });
it.each(LOCALES)("uses natural open-area labels in $code while preserving names and coordinates", ({ code }) => {
  useLocale.getState().setLocale(code);
  render(<Form />);
  expect(screen.getByRole("region", { name: t("layReservedAreasRegion") })).toBeTruthy();
  fireEvent.change(screen.getByLabelText(t("layAreaStartingPoint")), { target: { value: "pickup" } });
  fireEvent.click(screen.getByRole("button", { name: t("layAddReservedArea") }));
  fireEvent.click(screen.getByRole("button", { name: t("layAddReservedArea") }));
  expect(areas()).toEqual([original,
    { label: t("layAreaName_pickup"), x: 2, y: 6, width: 3, height: 2 },
    { label: `${t("layAreaName_pickup")} 2`, x: 2, y: 6, width: 3, height: 2 },
  ]);
  const snapshot = areas();
  act(() => useLocale.getState().setLocale(code === "fr" ? "ja" : "fr"));
  expect(areas()).toEqual(snapshot);
  expect((screen.getByLabelText(t("layAreaNameLabel", { number: 1 })) as HTMLInputElement).value).toBe(original.label);
  fireEvent.click(screen.getByRole("button", { name: t("layMoveAreaToPosition", { number: 1, position: t("layAreaPos_back_right") }) }));
  expect(areas()).toEqual([{ ...original, x: 9, y: 1 }, ...snapshot.slice(1)]);
  expect((screen.getByLabelText(t("layAreaField", { number: 1, field: t("layAreaStartColumn") })) as HTMLInputElement).value).toBe("10");
  expect(screen.getByRole("button", { name: t("laySwapAreaDims", { number: 1 }) }).matches(":disabled")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: t("layMoveAreaToPosition", { number: 1, position: t("layAreaPos_center") }) }));
  fireEvent.click(screen.getByRole("button", { name: t("laySwapAreaDims", { number: 1 }) }));
  expect(areas()).toEqual([{ ...original, x: 5, y: 3, width: 3, height: 2 }, ...snapshot.slice(1)]);
  const width = screen.getByLabelText(t("layAreaField", { number: 1, field: t("layWidth") }));
  fireEvent.change(width, { target: { value: "" } });
  expect(screen.getByRole("button", { name: t("layMoveAreaToPosition", { number: 1, position: t("layAreaPos_center") }) }).matches(":disabled")).toBe(true);
  fireEvent.change(width, { target: { value: "4" } });
  fireEvent.click(screen.getByRole("button", { name: t("layMoveAreaToPosition", { number: 1, position: t("layAreaPos_front_left") }) }));
  expect(areas()[0]).toEqual({ ...original, x: 1, y: 7, width: 4, height: 2 });
  fireEvent.click(screen.getByRole("button", { name: t("layRemoveArea", { number: 2 }) }));
  expect(areas()[1]).toEqual(snapshot[2]);
  act(() => useLocale.getState().setLocale(code));
  for (let count = 2; count < 8; count++) fireEvent.click(screen.getByRole("button", { name: t("layAddReservedArea") }));
  expect(areas()).toHaveLength(8);
  expect(new Set(areas().map(area => area.label)).size).toBe(8);
  expect(screen.getByRole("button", { name: t("layAddReservedArea") }).matches(":disabled")).toBe(true);
  expect(screen.getByText(t("layAreaLimitReached")).getAttribute("role")).toBe("status");
  fireEvent.click(screen.getByRole("button", { name: t("layRemoveArea", { number: 8 }) }));
  expect(screen.queryByText(t("layAreaLimitReached"))).toBeNull();
  expect(areas()[0]).toEqual({ ...original, x: 1, y: 7, width: 4, height: 2 });
});
