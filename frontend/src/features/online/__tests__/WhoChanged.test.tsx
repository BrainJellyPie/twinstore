// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { WhoChanged } from "../WhoChanged";

const summary = (site_id: string, site_name: string) => ({ site_id, site_name }) as online.VariantSummary;
const shopper = { id: "os0001", identity: "Retired teacher" } as online.OnlineShopper;
const result = {
  run_id: "r", variants: [summary("a", "Control store"), summary("b", "No fee")], shoppers: [shopper],
  comparisons: [{
    site_id: "b", site_name: "No fee", deltas: [], ad_lifts: [], won: 3, lost: 1, changed: 70,
    segments: [
      { dimension: "mission", value: "purchase", n: 20, control_conversion: 0.4, variant_conversion: 0.55, conversion_diff: 0.15,
        ci_low: 0.05, ci_high: 0.25, revenue_diff: 3.5 },
      { dimension: "device", value: "mobile", n: 12, control_conversion: 0.25, variant_conversion: 0.25, conversion_diff: 0,
        ci_low: -0.1, ci_high: 0.1, revenue_diff: 0 },
    ],
    switches: [{ shopper_id: "os0001", control_outcome: "left", variant_outcome: "purchased", control_total: 0, variant_total: 4200,
      control_exit: "checkout", variant_exit: "order_complete", control_thought: "A service fee at the very end? Forget it.",
      variant_thought: "" }],
  }],
} as unknown as online.OnlineRunResult;

beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => cleanup());

it("omits new comparison claims for saved reports without the segment analysis", () => {
  const previous = { ...result, comparisons: result.comparisons.map((c) => ({
    ...c, segments: [], switches: [], won: 0, lost: 0, changed: 0,
  })) };
  const view = render(<WhoChanged result={previous} money={String} onReplay={vi.fn()} onCompare={vi.fn()} />);
  expect(view.container.textContent).toBe("");
});

it("still shows measured zero changes when the segment analysis is present", () => {
  const measured = { ...result, comparisons: result.comparisons.map((c) => ({
    ...c, switches: [], won: 0, lost: 0, changed: 0,
  })) };
  render(<WhoChanged result={measured} money={String} onReplay={vi.fn()} onCompare={vi.fn()} />);
  expect(screen.getByText("Orders won: 0")).toBeTruthy();
  expect(screen.getByText("Orders lost: 0")).toBeTruthy();
});

it("shows orders won and lost, the groups a change helps, and why each changed visit ended", () => {
  const replay = vi.fn();
  const compare = vi.fn();
  render(<WhoChanged result={result} money={(x) => `$${(x / 100).toFixed(2)}`} onReplay={replay} onCompare={compare} />);
  expect(screen.getByText("Orders won: 3")).toBeTruthy();
  expect(screen.getByText("Orders lost: 1")).toBeTruthy();
  const buying = screen.getByText("Buy something").closest("tr")!;
  expect(buying.textContent).toContain("+15.0 pp");
  expect(buying.className).toContain("tone-good");
  expect(screen.queryByText("Mobile")).toBeNull(); // another breakdown
  fireEvent.click(screen.getByRole("button", { name: "Device" }));
  expect(screen.getByText("Mobile").closest("tr")!.className).not.toContain("tone");
  expect(screen.getByText("Retired teacher")).toBeTruthy();
  expect(screen.getByText("Shoppers whose visit ended differently: 70")).toBeTruthy();
  expect(screen.getByText("Listed (largest order changes first): 1")).toBeTruthy();
  expect(screen.getByText("“A service fee at the very end? Forget it.”")).toBeTruthy();
  expect(screen.getByText(/Ordered · \$42\.00/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Replay Retired teacher in No fee" }));
  expect(replay).toHaveBeenCalledWith(1, "os0001");
  fireEvent.click(screen.getByRole("button", { name: "Replay Retired teacher in Control store" }));
  expect(replay).toHaveBeenLastCalledWith(0, "os0001");
  fireEvent.click(screen.getByRole("button", { name: "Side by side for Retired teacher" }));
  expect(compare).toHaveBeenCalledWith(1, "os0001");
});
