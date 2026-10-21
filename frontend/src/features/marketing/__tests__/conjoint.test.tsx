// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { designConjoint, startConjoint, type ConjointReport } from "@/shared/api/marketing";
import { ConjointBuilder } from "../ConjointBuilder";
import { ConjointReportView } from "../ConjointReport";
import { defaultLineup, shareCurve, shares, utility } from "../conjoint";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), startConjoint: vi.fn(), designConjoint: vi.fn(), getStudyReading: vi.fn().mockResolvedValue(null),
}));
const withQueries = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
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
  render(<ConjointReportView projectId="p" report={REPORT} />, { wrapper: withQueries });
  expect(screen.getByText("What drives the choice")).toBeTruthy();
  expect(screen.getAllByText("Zero sugar").length).toBeGreaterThan(0);
  const before = screen.getAllByText(/^\d+ %$/).map((n) => n.textContent);
  fireEvent.change(screen.getByLabelText("Price of product A"), { target: { value: "249" } });
  expect(screen.getAllByText(/^\d+ %$/).map((n) => n.textContent)).not.toEqual(before);
  fireEvent.click(screen.getByRole("button", { name: /Add product/ }));
  expect(screen.getByLabelText("Price of product C")).toBeTruthy();
});

it.each([1, 3])("resets the simulator when switching to a study with %s attributes", (count) => {
  const view = render(<ConjointReportView projectId="p" report={REPORT} />, { wrapper: withQueries });
  fireEvent.change(screen.getByLabelText("Price of product A"), { target: { value: "249" } });
  fireEvent.click(screen.getByRole("button", { name: /Add product/ }));
  const attributes = [...REPORT.attributes, { name: "Brand", levels: ["Store", "Known"] }].slice(0, count);
  const next: ConjointReport = { ...REPORT, conjoint_id: "cjt_other", attributes, prices: [1000, 2000], price_mean: 1500,
    part_worths: attributes.flatMap((a) => a.levels.map((level, i) => pw(a.name, level, i ? 0.5 : -0.5))), segments: [] };
  view.rerender(<ConjointReportView projectId="p" report={next} />);
  expect(screen.queryByLabelText("Price of product C")).toBeNull();
  expect((screen.getByLabelText("Price of product A") as HTMLInputElement).value).toBe("2000");
  expect((screen.getByLabelText("Price of product B") as HTMLInputElement).value).toBe("1000");
  const choices = screen.getAllByRole("combobox") as HTMLSelectElement[];
  expect(choices).toHaveLength(count * 2);
  expect(choices.slice(0, count).map((choice) => choice.value)).toEqual(Array(count).fill("1"));
  fireEvent.change(choices[count - 1]!, { target: { value: "0" } });
  expect(choices[count - 1]!.value).toBe("0");
  // Refreshing the same completed study should preserve the user's current comparison.
  fireEvent.change(screen.getByLabelText("Price of product A"), { target: { value: "1750" } });
  view.rerender(<ConjointReportView projectId="p" report={{ ...next }} />);
  expect((screen.getByLabelText("Price of product A") as HTMLInputElement).value).toBe("1750");
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

it.each([2, 3, 4].flatMap((options) => [false, true].map((priced) => ({ options, priced }))))(
  "previews distinct options in a two-by-two design ($options options, priced=$priced)", ({ options, priced }) => {
    render(<QueryClientProvider client={new QueryClient()}>
      <ConjointBuilder projectId="project" personaCount={60} onStarted={vi.fn()} initial={{
        product: "tea", attributes: priced ? [REPORT.attributes[0]!] : REPORT.attributes,
        prices: priced ? [0, 199] : [], currency: "USD", tasks: 3, options, none_option: true,
        panel: 10, age_groups: [], genders: [], model: "",
      }} />
    </QueryClientProvider>);
    const sample = within(screen.getByText("A sample choice task").closest("section")!);
    for (let draw = 0; draw < 8; draw++) {
      const profiles = sample.getAllByRole("list").map((list) => within(list).getAllByRole("listitem").map((item) => item.textContent).join(" | "));
      expect(profiles).toHaveLength(options);
      expect(new Set(profiles).size).toBe(options);
      fireEvent.click(sample.getByRole("button", { name: "Another" }));
    }
    expect(startConjoint).not.toHaveBeenCalled();
  },
);

it.each(["", "Regular"])("keeps incomplete drafts editable with insufficient distinct profiles (%s)", (levels) => {
  render(<QueryClientProvider client={new QueryClient()}>
    <ConjointBuilder projectId="project" personaCount={60} onStarted={vi.fn()} />
  </QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Levels of attribute 1"), { target: { value: levels } });
  fireEvent.change(screen.getByLabelText("Levels of attribute 2"), { target: { value: levels } });
  fireEvent.click(screen.getByRole("button", { name: "Another" }));
  expect((screen.getByRole("button", { name: "Field the study" }) as HTMLButtonElement).disabled).toBe(true);
});

it("drafts the study from a question, in the study's currency, and keeps it editable", async () => {
  vi.mocked(designConjoint).mockResolvedValue({
    name: "Zero-sugar tea", product: "a bottle of iced tea", context: "In the drinks fridge.",
    attributes: [{ name: "Sugar", levels: ["Regular", "Zero sugar"] }, { name: "Size", levels: ["500 ml", "1 L"] }],
    prices: [1500, 1800, 2100], currency: "KRW", rationale: "Sugar and size are what the question is about.",
    comparable: ["Green tea 500ml 1,600원"],
  });
  render(<QueryClientProvider client={new QueryClient()}>
    <ConjointBuilder projectId="project" personaCount={60} defaultCurrency="KRW" setupId="setup_1" onStarted={vi.fn()} />
  </QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Question for the study"), { target: { value: "Would people pay more for zero-sugar tea?" } });
  fireEvent.click(screen.getByRole("button", { name: "Draft the study" }));
  await screen.findByText(/Sugar and size are what the question is about\./);
  expect(designConjoint).toHaveBeenCalledWith("project", { question: "Would people pay more for zero-sugar tea?", setup_id: "setup_1", currency: "KRW" });
  expect(screen.getByText(/Prices set against Green tea 500ml 1,600원\./)).toBeTruthy();
  expect((screen.getByLabelText("Price levels") as HTMLInputElement).value).toBe("1500, 1800, 2100");
  expect((screen.getByLabelText("Levels of Size") as HTMLInputElement).value).toBe("500 ml, 1 L");
  expect((screen.getByPlaceholderText("a bottle of iced tea") as HTMLInputElement).value).toBe("a bottle of iced tea");
});

it.each([["JPY", "150, 180, 200, 230"], ["KRW", "1490, 1790, 1990, 2290"], ["VND", ""]])(
  "gives example prices in the study's currency (%s)", (currency, expected) => {
    render(<QueryClientProvider client={new QueryClient()}>
      <ConjointBuilder projectId="project" personaCount={60} defaultCurrency={currency} onStarted={vi.fn()} />
    </QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Iced tea" }));
    expect((screen.getByLabelText("Price levels") as HTMLInputElement).value).toBe(expected);
  },
);

it("drafts the study from a request routed by the command palette and keeps the reply", async () => {
  vi.mocked(designConjoint).mockResolvedValue({
    name: "Oat milk", product: "a carton of oat milk", context: "In the dairy fridge.",
    attributes: [{ name: "Brand", levels: ["Store", "Oatly"] }], prices: [1500, 1800], currency: "KRW", rationale: "Brand is the question.",
    comparable: [],
  });
  render(<QueryClientProvider client={new QueryClient()}>
    <ConjointBuilder projectId="project" personaCount={60} defaultCurrency="KRW" setupId="setup_1" onStarted={vi.fn()}
      prefill={{ id: 3, text: "Would people pay more for a branded oat milk?" }} />
  </QueryClientProvider>);
  await screen.findByText(/Brand is the question\./);
  expect(designConjoint).toHaveBeenCalledTimes(1);
  expect(designConjoint).toHaveBeenCalledWith("project", { question: "Would people pay more for a branded oat milk?", setup_id: "setup_1", currency: "KRW" });
  expect((screen.getByLabelText("Question for the study") as HTMLTextAreaElement).value).toBe("Would people pay more for a branded oat milk?");
  expect((screen.getByLabelText("Price levels") as HTMLInputElement).value).toBe("1500, 1800");
});
