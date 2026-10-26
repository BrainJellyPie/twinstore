// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, expect, it } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

import { useLocale } from "@/shared/i18n/i18n";
import { translate } from "@/shared/i18n/translate";
import { storeTypeLabel } from "@/shared/i18n/storeLabels";
import { StoreInfoFields } from "../components/StoreInfoFields";

afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });

function Form() {
  const [storeType, setStoreType] = useState("convenience");
  return <>
    <StoreInfoFields name="" description="" address="" storeType={storeType} onNameChange={() => {}} onDescriptionChange={() => {}}
      onAddressChange={() => {}} onStoreTypeChange={setStoreType} />
    <output data-testid="saved">{storeType}</output>
    <button onClick={() => setStoreType("books")}>Use books template</button>
    <button onClick={() => setStoreType("cafe")}>Use cafe template</button>
  </>;
}

it("shows a category id by its label in the selected language and keeps the id until the field is edited", () => {
  useLocale.getState().setLocale("ko");
  render(<Form />);
  const field = screen.getByLabelText("매장 유형") as HTMLInputElement;
  expect(field.value).toBe("편의점");
  expect(screen.getByTestId("saved").textContent).toBe("convenience");
  fireEvent.change(field, { target: { value: "24시 편의점" } });
  expect(field.value).toBe("24시 편의점");
  expect(screen.getByTestId("saved").textContent).toBe("24시 편의점");
});

it.each(["en", "ko", "zh", "ja", "es", "fr"] as const)("preserves custom typing through a category-id prefix in %s", (locale) => {
  useLocale.getState().setLocale(locale);
  render(<Form />);
  const field = screen.getByLabelText(translate(locale, "storeType")) as HTMLInputElement;
  fireEvent.change(field, { target: { value: "caf" } });
  fireEvent.change(field, { target: { value: `${field.value}e` } });
  expect(field.value).toBe("cafe");
  fireEvent.change(field, { target: { value: `${field.value}teria` } });
  expect(field.value).toBe("cafeteria");
  expect(screen.getByTestId("saved").textContent).toBe("cafeteria");
});

it("preserves a manually entered id across locale changes and relabels a later template selection", () => {
  useLocale.getState().setLocale("ko");
  render(<Form />);
  const field = screen.getByLabelText("매장 유형") as HTMLInputElement;
  fireEvent.change(field, { target: { value: "cafe" } });
  act(() => useLocale.getState().setLocale("ja"));
  expect(field.value).toBe("cafe");
  expect(screen.getByTestId("saved").textContent).toBe("cafe");
  fireEvent.click(screen.getByRole("button", { name: "Use books template" }));
  expect(field.value).toBe(storeTypeLabel("books", "ja"));
  fireEvent.click(screen.getByRole("button", { name: "Use cafe template" }));
  expect(field.value).toBe(storeTypeLabel("cafe", "ja"));
  expect(screen.getByTestId("saved").textContent).toBe("cafe");
});
