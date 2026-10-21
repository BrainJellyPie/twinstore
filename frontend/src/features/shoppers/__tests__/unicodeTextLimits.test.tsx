// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import type { Journey } from "@/shared/api/interview";
import { ConjointBuilder } from "@/features/marketing/ConjointBuilder";
import { ScenarioEditor } from "@/features/runs/components/ScenarioEditor";
import { GroupInterviewPanel } from "../GroupInterview";
import { InterviewChat } from "../InterviewChat";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(),
  getModels: vi.fn().mockResolvedValue([]), getScenarios: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(),
  listGroups: vi.fn().mockResolvedValue([]),
  getInterview: vi.fn().mockResolvedValue({ run_id: "r", persona_id: "p", model: "fake", messages: [] }),
  suggestQuestions: vi.fn().mockResolvedValue({ run_id: "r", persona_id: "p", model: "fake", messages: [], suggested_questions: [] }),
}));
beforeEach(() => Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const journey: Journey = {
  run_id: "r", day: 1, arrival_time: "09:00:00", leave_time: "09:01:00", engine_type: "rule_based", currency: "USD",
  total_spent: 0, units: 0, steps: [], path: [], shelves: {},
  persona: { id: "p", day: 1, identity: "Shopper", age_group: "30s", gender: "Female", description: "", intent: "", purpose: "", arrival_hour: 9, preferred_categories: [], budget_min: 0, budget_max: 0, behavior_tendency: "" },
};
const FIELDS = [
  { field: "scenario", limit: 800 }, { field: "interview", limit: 600 }, { field: "group", limit: 600 },
  { field: "study question", limit: 500 }, { field: "product", limit: 160 }, { field: "context", limit: 300 }, { field: "attribute", limit: 40 },
] as const;
type Field = typeof FIELDS[number]["field"];
function mount(field: Field) {
  const element = field === "scenario" ? <ScenarioEditor value={null} onChange={vi.fn()} projectId="p" setupId="s" />
    : field === "interview" ? <InterviewChat projectId="p" runId="r" journey={journey} onCite={vi.fn()} />
    : field === "group" ? <GroupInterviewPanel projectId="p" runId="r" currency="USD" onOpen={vi.fn()} onBack={vi.fn()} />
    : <ConjointBuilder projectId="p" personaCount={60} onStarted={vi.fn()} />;
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{element}</QueryClientProvider>);
  if (field === "scenario") return screen.getByLabelText("Describe the day");
  if (field === "interview" || field === "group") return screen.getByRole("textbox");
  if (field === "study question") return screen.getByLabelText("Question for the study");
  if (field === "product") return screen.getByPlaceholderText("a bottle of iced tea");
  if (field === "context") return screen.getByPlaceholderText("Sold in the drinks fridge next to the sodas.");
  return screen.getByLabelText("Attribute 1 name");
}
const cases = FIELDS.flatMap(({ field, limit }) => [
  { field, kind: "ASCII overflow", text: "a".repeat(limit + 3), expected: "a".repeat(limit) },
  { field, kind: "emoji at the boundary", text: "a".repeat(limit - 1) + "🛒", expected: "a".repeat(limit - 1) + "🛒" },
  { field, kind: "emoji before overflow", text: "a".repeat(limit - 1) + "🛒x", expected: "a".repeat(limit - 1) + "🛒" },
  { field, kind: "all supplementary characters", text: "𠮷".repeat(limit + 2), expected: "𠮷".repeat(limit) },
]);
it.each(cases)("keeps complete characters in $field: $kind", ({ field, text, expected }) => {
  const input = mount(field);
  fireEvent.change(input, { target: { value: text } });
  expect((input as HTMLInputElement).value).toBe(expected);
});

it.each([
  { field: "scenario" as const, count: 2, disabled: true }, { field: "scenario" as const, count: 3, disabled: false },
  { field: "study question" as const, count: 4, disabled: true }, { field: "study question" as const, count: 5, disabled: false },
])("uses the server's character count for the minimum $field length: $count", ({ field, count, disabled }) => {
  const input = mount(field);
  fireEvent.change(input, { target: { value: "🛒".repeat(count) } });
  expect((screen.getByRole("button", { name: field === "scenario" ? "Set up" : "Draft the study" }) as HTMLButtonElement).disabled).toBe(disabled);
});

it("preserves a complete character at the end of a duplicated study's name", () => {
  const name = "a".repeat(79) + "🛒";
  render(<QueryClientProvider client={new QueryClient()}><ConjointBuilder projectId="p" personaCount={60} onStarted={vi.fn()} initial={{ name, product: "Tea", context: "", attributes: [{ name: "Size", levels: ["Small", "Large"] }], prices: [100, 200], currency: "USD", tasks: 8, options: 3, none_option: true, panel: 60, age_groups: [], genders: [], model: "" }} /></QueryClientProvider>);
  expect((screen.getByPlaceholderText("Study name (optional)") as HTMLInputElement).value).toBe(name);
});
