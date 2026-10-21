// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { startConjoint, type ConjointReport } from "@/shared/api/marketing";
import { ConjointBuilder } from "../ConjointBuilder";
import { ConjointReportView } from "../ConjointReport";
import { defaultLineup, shareCurve, shares, utility } from "../conjoint";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), startConjoint: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const pw = (attribute: string, level: string, utility: number, wtp: number | null = null) =>
  ({ attribute, level, utility, ci_low: utility - 0.1, ci_high: utility + 0.1, wtp, wtp_low: null, wtp_high: null });

const REPORT: ConjointReport = {
  conjoint_id: "cjt_1", name: "Iced tea", model: "openai/gpt-4o-mini", product: "a bottle of iced tea", currency: "USD",
  attributes: [{ name: "Sugar", levels: ["Regular", "Zero sugar"] }, { name: "Size", levels: ["330 ml", "500 ml"] }],
  prices: [149, 199, 249], options: 3, none_option: true, respondents: 60, errors: 0, none_share: 0.12,
  part_worths: [pw("Sugar", "Regular", -0.4), pw("Sugar", "Zero sugar", 0.4, 40), pw("Size", "330 ml", -0.1), pw("Size", "500 ml", 0.1, 10),
    pw("Price", "$1.49", 1), pw("Price", "$1.99", 0), pw("Price", "$2.49", -1)],
  importances: [{ attribute: "Price", importance: 0.6, ci_low: 0.5, ci_high: 0.7 }, { attribute: "Sugar", importance: 0.3, ci_low: 0.2, ci_high: 0.4 },
    { attribute: "Size", importance: 0.1, ci_low: 0.05, ci_high: 0.15 }],
  price_slope: -0.02, price_mean: 199, none_utility: -1,
  fit: { choices: 480, log_likelihood: -400, null_log_likelihood: -665, mcfadden_r2: 0.4, hit_rate: 0.62, chance_rate: 0.25 },
  segments: [{ segment: "age 20s", n: 30, importances: { Price: 0.7, Sugar: 0.2, Size: 0.1 }, none_share: 0.1 }],
  answers: [], verbatims: ["Zero sugar mattered most."], notes: ["Synthetic respondents."], seconds: 42,
};

it("simulates logit shares, including none, at any price in the tested range", () => {
  const best = { levels: [1, 1], price: 199 };
  expect(utility(REPORT, best)).toBeCloseTo(0.5);
  expect(utility(REPORT, { levels: [1, 1], price: 149 })).toBeCloseTo(1.5);
  const [a, none] = shares(REPORT, [best]);
  expect(a).toBeCloseTo(Math.exp(0.5) / (Math.exp(0.5) + Math.exp(-1)));
  expect(a! + none!).toBeCloseTo(1);
  expect(shares(REPORT, [best], false)).toEqual([1]);
  const curve = shareCurve(REPORT, [best, { levels: [0, 0], price: 149 }], 4);
  expect(curve.map((c) => c.price)).toEqual([149, 174, 199, 224, 249]);
  expect(curve[0]!.share).toBeGreaterThan(curve[4]!.share);
  expect(defaultLineup(REPORT)).toEqual([{ levels: [1, 1], price: 199 }, { levels: [0, 0], price: 149 }]);
});

it("shows importance, part-worths and a live simulator", () => {
  render(<ConjointReportView projectId="p" report={REPORT} />);
  expect(screen.getByText("What drives the choice")).toBeTruthy();
  expect(screen.getAllByText("Zero sugar").length).toBeGreaterThan(0);
  const before = screen.getAllByText(/^\d+ %$/).map((n) => n.textContent);
  fireEvent.change(screen.getByLabelText("Price of product A"), { target: { value: "249" } });
  expect(screen.getAllByText(/^\d+ %$/).map((n) => n.textContent)).not.toEqual(before);
  fireEvent.click(screen.getByRole("button", { name: /Add product/ }));
  expect(screen.getByLabelText("Price of product C")).toBeTruthy();
});

it("sends attributes, price levels in minor units and the design", async () => {
  vi.mocked(startConjoint).mockResolvedValue({ job_id: "cjt_test", kind: "conjoint", name: "Test", status: "pending",
    stage: "queued", progress: 0, error: "", created_at: "", finished_at: "" });
  const started = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}>
    <ConjointBuilder projectId="project" personaCount={60} defaultCurrency="USD" onStarted={started} />
  </QueryClientProvider>);
  const field = screen.getByRole("button", { name: "Field the study" }) as HTMLButtonElement;
  expect(field.disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Iced tea" }));
  fireEvent.change(screen.getByLabelText("Price levels"), { target: { value: "1.49, 1.99, x" } });
  expect(screen.getByText("Price levels must be amounts like 1.99.")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Price levels"), { target: { value: "1.49, 1.99" } });
  fireEvent.click(field);
  await waitFor(() => expect(started).toHaveBeenCalled());
  const req = vi.mocked(startConjoint).mock.calls[0]![1];
  expect(req.prices).toEqual([149, 199]);
  expect(req.attributes[0]).toEqual({ name: "Sugar", levels: ["Regular", "Less sugar", "Zero sugar"] });
  expect([req.tasks, req.options, req.none_option, req.currency]).toEqual([8, 3, true, "USD"]);
});
