// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { explainComparison, type ComparisonReport, type MetricComparison } from "@/shared/api/client";
import { CompareDialog } from "../CompareDialog";

const state = vi.hoisted(() => ({ report: null as ComparisonReport | null, currency: undefined as string | undefined }));
vi.mock("../../hooks", () => ({
  useProjectRuns: () => ({ data: ["run_a", "run_b"].map((run_id) => ({
    run_id, status: "completed", setup_id: "s1", created_at: "2026-10-21T10:00:00Z",
    summary: state.currency ? { currency: state.currency } : undefined,
  })) }),
  useCompare: () => ({ data: state.report, isLoading: false, isError: false }),
}));
vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), explainComparison: vi.fn(),
}));
afterEach(() => { cleanup(); state.currency = undefined; });

function show(overrides: Partial<MetricComparison> = {}, reportCurrency?: string) {
  state.report = {
    run_a: "run_a", run_b: "run_b", paired_customers: 100,
    unpaired_a: 0, unpaired_b: 0, n_bootstrap: 2000, confidence: 0.95, notes: [], currency: reportCurrency,
    metrics: [{
      metric: "spend", mean_a: 0, mean_b: 500, diff: 500, rel_diff: 0,
      ci_low: 200, ci_high: 800, prob_b_greater: 1, sd_paired_diff: 50,
      n_for_5pct_effect: 0, ...overrides,
    }],
  };
  render(<QueryClientProvider client={new QueryClient()}>
    <CompareDialog open onOpenChange={() => {}} projectId="p" layouts={[]} defaultRunId="run_b" />
  </QueryClientProvider>);
}

it("shows absolute spend gains and their interval when baseline spend is zero", () => {
  show();
  expect(screen.getByText("Spend per visitor: +$5.00")).toBeTruthy();
  expect(screen.getByText("+$2.00 … +$8.00")).toBeTruthy();
  const row = screen.getByText("Spend / visitor").closest("tr")!;
  const marker = row.querySelector("circle")!;
  const zero = row.querySelector("line")!;
  expect(Number(marker.getAttribute("cx"))).toBeGreaterThan(Number(zero.getAttribute("x1")));
});

it("shows spend per visitor as money in the run's currency, without a minor-unit footnote", () => {
  show({ mean_a: 845, mean_b: 862.4, diff: 17.4, rel_diff: 17.4 / 845 });
  const row = screen.getByText("Spend / visitor").closest("tr")!;
  expect([...row.querySelectorAll("td")].slice(1, 3).map((cell) => cell.textContent)).toEqual(["$8.45", "$8.62"]);
  expect(screen.getByRole("dialog").textContent).not.toMatch(/minor unit/);
  cleanup();
  state.currency = "KRW";
  show({ mean_a: 4200, mean_b: 4350, diff: 150, rel_diff: 150 / 4200 });
  const krw = screen.getByText("Spend / visitor").closest("tr")!;
  expect([...krw.querySelectorAll("td")].slice(1, 3).map((cell) => cell.textContent)).toEqual(["₩4,200", "₩4,350"]);
});

it("keeps relative changes for a nonzero baseline", () => {
  show({ mean_a: 1000, mean_b: 1500, rel_diff: 0.5 });
  expect(screen.getByText("Spend per visitor: +50.0%")).toBeTruthy();
  expect(screen.getByText("+20.0% … +80.0%")).toBeTruthy();
  expect(screen.getByText("100 paired customers · 2,000 bootstrap draws.")).toBeTruthy();
});

it("explains zero baselines in the footnote only when a row has one", () => {
  show();
  expect(screen.getByRole("dialog").textContent).toMatch(/With a zero baseline, intervals show absolute changes/);
});

it.each(["KRW", "JPY", "USD"].flatMap(currency =>
  [undefined, "USD", "KRW"].map(summary => ({ currency, summary })),
))("uses the report's $currency even with summary currency $summary", ({ currency, summary }) => {
  state.currency = summary;
  show({ mean_a: 4200, mean_b: 4350, diff: 150, rel_diff: 150 / 4200 }, currency);
  const row = screen.getByText("Spend / visitor").closest("tr")!;
  const expected = currency === "KRW" ? ["₩4,200", "₩4,350"]
    : currency === "JPY" ? ["¥4,200", "¥4,350"] : ["$42.00", "$43.50"];
  expect([...row.querySelectorAll("td")].slice(1, 3).map(cell => cell.textContent)).toEqual(expected);
});

it.each([
  ["KRW", "Spend per visitor: +₩500", "+₩200 … +₩800"],
  ["JPY", "Spend per visitor: +¥500", "+¥200 … +¥800"],
  ["USD", "Spend per visitor: +$5.00", "+$2.00 … +$8.00"],
])("uses report currency %s for zero-baseline headlines and intervals", (currency, headline, interval) => {
  state.currency = currency === "USD" ? "KRW" : "USD";
  show({}, currency);
  expect(screen.getByText(headline)).toBeTruthy();
  expect(screen.getByText(interval)).toBeTruthy();
});

it.each([undefined, "", "   "])("keeps the summary fallback for older report currency %s", currency => {
  state.currency = "KRW";
  show({}, currency);
  expect(screen.getByText("Spend per visitor: +₩500")).toBeTruthy();
});

it("shows a zero absolute difference when neither run has purchases", () => {
  show({ mean_b: 0, diff: 0, ci_low: 0, ci_high: 0, prob_b_greater: 0 });
  expect(screen.getByText("Spend per visitor: $0.00")).toBeTruthy();
  expect(screen.getByText("$0.00 … $0.00")).toBeTruthy();
  expect(screen.getByRole("dialog").textContent).not.toMatch(/NaN|Infinity/);
});

it("labels absolute conversion gains in percentage points", () => {
  show({ metric: "bought", mean_b: 0.5, diff: 0.5, ci_low: 0.2, ci_high: 0.8 });
  expect(screen.getByText("+20.0 pp … +80.0 pp")).toBeTruthy();
});

it.each(["spend", "units", "bought", "impulse_spend", "visit_sec", "path_tiles"].flatMap(metric =>
  [0, 10].map(mean_b => ({ metric, mean_b })),
))("withholds undefined relative sample sizes for $metric with B=$mean_b", ({ metric, mean_b }) => {
  show({ metric, mean_a: 0, mean_b, diff: mean_b, n_for_5pct_effect: 0 });
  const cell = screen.getByRole("table").querySelector("tbody tr")!.lastElementChild!;
  expect(cell.textContent).toBe("—");
  expect(cell.getAttribute("title")).toMatch(/zero baseline/i);
});

it.each([1, 100, 12345])("preserves an available relative sample size of %s", count => {
  show({ mean_a: 100, mean_b: 110, diff: 10, rel_diff: 0.1, n_for_5pct_effect: count });
  const cell = screen.getByRole("table").querySelector("tbody tr")!.lastElementChild!;
  expect(cell.textContent).toBe(count.toLocaleString());
});


it("explains the difference on request, with the figures it used", async () => {
  vi.mocked(explainComparison).mockResolvedValue({ summary: "B sells more drinks.", where: "Drink 3 gains 40 buyers.",
    caveats: "Snacks are within noise.", figures: ["Drink 3 1027 / 917"] });
  show({ mean_a: 1000, mean_b: 1500, rel_diff: 0.5 });
  fireEvent.click(screen.getByRole("button", { name: "Explain the difference" }));
  expect(await screen.findByText("B sells more drinks.")).toBeTruthy();
  expect(explainComparison).toHaveBeenCalledWith("p", "run_a", "run_b");
  expect(screen.getByRole("list", { name: "Figures used" }).textContent).toContain("Drink 3 1027 / 917");
});

it("cuts long run names with an ellipsis, keeps the full name as a tooltip and points to the hidden columns", () => {
  show();
  for (const name of ["Baseline run (A)", "Variant run (B)"]) {
    const trigger = screen.getByRole("combobox", { name });
    const full = trigger.getAttribute("title");
    expect(full).toMatch(/^s1 — /);
    expect(trigger.querySelector(".truncate")?.textContent).toBe(full);
  }
  expect(screen.getByText("Scroll sideways for the interval, change, P and n columns.")).toBeTruthy();
  const region = screen.getByRole("region", { name: "Run comparison metrics" });
  expect(region.querySelector("tbody td")!.className).toContain("sticky");
  // Only the metrics the server sent are listed (an older run without purchase origins has no impulse row).
  expect(region.querySelectorAll("tbody tr")).toHaveLength(1);
});

it("says the server's notes in the user's language, and keeps unknown ones as sent", async () => {
  const { useLocale } = await import("@/shared/i18n/i18n");
  useLocale.getState().setLocale("ko");
  try {
    show();
    state.report = {
      ...state.report!,
      notes: ["In run_a each shopper had the store alone …", "A note this version does not know"],
      note_codes: [{ code: "store_alone", params: { run: "run_a" } }, { code: "something_new", params: {} }],
    };
    cleanup();
    render(<QueryClientProvider client={new QueryClient()}>
      <CompareDialog open onOpenChange={() => {}} projectId="p" layouts={[]} defaultRunId="run_b" />
    </QueryClientProvider>);
    const text = screen.getByRole("dialog").textContent ?? "";
    // The run is named as in the run pickers, not by its id.
    expect(text).toContain("s1 — LLM · 최종 · 10월 21일에서는 고객마다 매장을 혼자 썼습니다");
    expect(text).not.toContain("run_a");
    expect(text).toContain("A note this version does not know");
    expect(text).not.toContain("each shopper had the store alone");
  } finally {
    useLocale.getState().setLocale("en");
  }
});

it.each([
  [0, 2290, "2,290 customers only in s1 — LLM · final · Oct 21 were excluded"],
  [5, 0, "5 customers only in"],
  [5, 7, "5 customers only in"],
])("names only the run that left customers out (%i and %i unpaired)", (onlyA, onlyB, expected) => {
  show();
  state.report = {
    ...state.report!,
    notes: ["English fallback"],
    note_codes: [{ code: "unpaired", params: { onlyA, runA: "run_a", onlyB, runB: "run_a" } }],
  };
  cleanup();
  render(<QueryClientProvider client={new QueryClient()}>
    <CompareDialog open onOpenChange={() => {}} projectId="p" layouts={[]} defaultRunId="run_b" />
  </QueryClientProvider>);
  const text = screen.getByRole("dialog").textContent ?? "";
  expect(text).toContain(expected);
  expect(text).not.toMatch(/\b0 customers only in|and 0 only in/);
  if (onlyA && onlyB) expect(text).toContain("and 7 only in");
});
