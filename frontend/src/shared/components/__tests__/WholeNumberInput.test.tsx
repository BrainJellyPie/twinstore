// @vitest-environment jsdom
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { WholeNumberInput } from "../WholeNumberInput";

afterEach(cleanup);

function Field({ start }: { start: number }) {
  const [value, setValue] = useState(start);
  return <><WholeNumberInput aria-label="Steps" min={3} max={80} value={value} onChange={setValue} /><output>{value}</output></>;
}

it("takes a number typed into an emptied field as typed, not after the minimum", () => {
  render(<Field start={24} />);
  const field = screen.getByRole("spinbutton", { name: "Steps" });
  fireEvent.change(field, { target: { value: "" } });
  expect((field as HTMLInputElement).value).toBe("");
  fireEvent.change(field, { target: { value: "4" } });
  fireEvent.change(field, { target: { value: "40" } });
  expect((field as HTMLInputElement).value).toBe("40");
  expect(screen.getByRole("status").textContent).toBe("40");
});

it("brings a number outside the limits back within them on leaving the field", () => {
  render(<Field start={24} />);
  const field = screen.getByRole("spinbutton", { name: "Steps" });
  fireEvent.change(field, { target: { value: "500" } });
  expect(screen.getByRole("status").textContent).toBe("24");
  fireEvent.blur(field);
  expect((field as HTMLInputElement).value).toBe("80");
  fireEvent.change(field, { target: { value: "1" } });
  fireEvent.blur(field);
  expect((field as HTMLInputElement).value).toBe("3");
});

it("keeps the last number when the field is left empty", () => {
  render(<Field start={24} />);
  const field = screen.getByRole("spinbutton", { name: "Steps" });
  fireEvent.change(field, { target: { value: "" } });
  fireEvent.blur(field);
  expect((field as HTMLInputElement).value).toBe("24");
});

it.each(["40", "", "500"])("follows an external value change while the field contains %j", (text) => {
  const onChange = vi.fn();
  const { rerender } = render(<WholeNumberInput aria-label="Steps" min={3} max={80} value={24} onChange={onChange} />);
  const field = screen.getByRole("spinbutton", { name: "Steps" }) as HTMLInputElement;
  fireEvent.change(field, { target: { value: text } });
  // Accept a valid manual edit, then apply a separately supplied setting.
  if (text === "40") rerender(<WholeNumberInput aria-label="Steps" min={3} max={80} value={40} onChange={onChange} />);
  rerender(<WholeNumberInput aria-label="Steps" min={3} max={80} value={12} onChange={onChange} />);
  expect(field.value).toBe("12");
  fireEvent.blur(field);
  expect(onChange).toHaveBeenLastCalledWith(12);
  // Returning to the previous value must not revive the discarded text.
  rerender(<WholeNumberInput aria-label="Steps" min={3} max={80} value={24} onChange={onChange} />);
  expect(field.value).toBe("24");
});
