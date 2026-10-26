// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { Journey, JourneyStep } from "@/shared/api/interview";
import { useLocale } from "@/shared/i18n/i18n";
import { JourneySteps } from "../JourneyView";

beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(cleanup);

const step = { index: 1, time: "10:05", elapsed_sec: 0, action: "browse", rack_id: "r1", rack: "Drinks", face: "N", product_sku: "",
  product_name: "", price: 0, quantity: 0, origin: "", thought: "", sees_products: true } as unknown as JourneyStep;
const journey = { run_id: "run1", currency: "USD", steps: [step] } as unknown as Journey;

it.each(["Escape", "button"])("opens the shelf picture with focus on Close, and restores focus after %s", async (method) => {
  render(<JourneySteps projectId="p" journey={journey} active={new Set()} onHover={() => {}} />);
  const picture = screen.getByRole("button", { name: /Drinks/ });
  picture.focus();
  fireEvent.click(picture);
  const dialog = screen.getByRole("dialog");
  expect(dialog.getAttribute("aria-modal")).toBe("true");
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close" }));
  fireEvent.click(dialog.querySelector("img")!);
  expect(screen.getByRole("dialog")).toBe(dialog);
  if (method === "Escape") fireEvent.keyDown(document.activeElement!, { key: "Escape" });
  else fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  await waitFor(() => expect(document.activeElement).toBe(picture));
});

it.each([false, true])("keeps keyboard focus in the enlarged picture (shift=%s)", (shiftKey) => {
  render(<><button>Outside action</button><JourneySteps projectId="p" journey={journey} active={new Set()} onHover={() => {}} /></>);
  fireEvent.click(screen.getByRole("button", { name: /Drinks/ }));
  const close = screen.getByRole("button", { name: "Close" });
  // A single-control modal must prevent the browser's default Tab from leaving it.
  expect(fireEvent.keyDown(close, { key: "Tab", shiftKey })).toBe(false);
  expect(document.activeElement).toBe(close);
});

it("blocks focus from moving to an action behind the enlarged picture", () => {
  render(<><button>Outside action</button><JourneySteps projectId="p" journey={journey} active={new Set()} onHover={() => {}} /></>);
  const outside = screen.getByRole("button", { name: "Outside action" });
  fireEvent.click(screen.getByRole("button", { name: /Drinks/ }));
  outside.focus();
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close" }));
});
