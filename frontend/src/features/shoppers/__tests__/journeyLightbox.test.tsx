// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import type { Journey, JourneyStep } from "@/shared/api/interview";
import { useLocale } from "@/shared/i18n/i18n";
import { JourneySteps } from "../JourneyView";

beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(cleanup);

const step = { index: 1, time: "10:05", elapsed_sec: 0, action: "browse", rack_id: "r1", rack: "Drinks", face: "N", product_sku: "",
  product_name: "", price: 0, quantity: 0, origin: "", thought: "", sees_products: true } as unknown as JourneyStep;
const journey = { run_id: "run1", currency: "USD", steps: [step] } as unknown as Journey;

it("opens the shelf picture with focus on Close, and gives focus back to the picture when closed", () => {
  render(<JourneySteps projectId="p" journey={journey} active={new Set()} onHover={() => {}} />);
  const picture = screen.getByRole("button", { name: /Drinks/ });
  picture.focus();
  fireEvent.click(picture);
  const dialog = screen.getByRole("dialog");
  expect(dialog.getAttribute("aria-modal")).toBe("true");
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close" }));
  fireEvent.keyDown(window, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(picture);
});
