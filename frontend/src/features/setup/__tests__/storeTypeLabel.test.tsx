// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { useLocale } from "@/shared/i18n/i18n";
import { StoreInfoFields } from "../components/StoreInfoFields";

afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });

function Form() {
  const [storeType, setStoreType] = useState("convenience");
  return <>
    <StoreInfoFields name="" description="" address="" storeType={storeType} onNameChange={() => {}} onDescriptionChange={() => {}}
      onAddressChange={() => {}} onStoreTypeChange={setStoreType} />
    <output data-testid="saved">{storeType}</output>
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
