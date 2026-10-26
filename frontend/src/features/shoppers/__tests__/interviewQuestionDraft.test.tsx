// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { askShopper, getInterview, suggestQuestions, type Interview, type Journey } from "@/shared/api/interview";
import { InterviewChat } from "../InterviewChat";

vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(),
  askShopper: vi.fn(), clearInterview: vi.fn(), getInterview: vi.fn(), suggestQuestions: vi.fn(),
}));
vi.mock("@/shared/api/client", () => ({
  BASE: "", getModels: vi.fn().mockResolvedValue([]),
  // A provider is set up, so no "needs a model" hint shows.
  getModelSetup: vi.fn().mockResolvedValue({ cloud_providers: ["openai"], local: { state: "off" } }),
  startLocalModel: vi.fn(), stopLocalModel: vi.fn(),
}));

const journey: Journey = {
  run_id: "r", day: 1, arrival_time: "09:00:00", leave_time: "09:01:00", engine_type: "rule_based",
  currency: "USD", total_spent: 0, units: 0, steps: [], path: [], shelves: {},
  persona: { id: "p", day: 1, identity: "Shopper", age_group: "30s", gender: "Female", description: "",
    intent: "", purpose: "", arrival_hour: 9, preferred_categories: [], budget_min: 0, budget_max: 0, behavior_tendency: "" },
};
const empty: Interview = { run_id: "r", persona_id: "p", model: "fake", messages: [] };
const answered: Interview = { ...empty, messages: [
  { role: "interviewer", text: "Why?", steps: [], created_at: "" },
  { role: "shopper", text: "I was in a hurry.", steps: [], created_at: "" },
] };

beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
  vi.mocked(suggestQuestions).mockRejectedValue(new Error("no model"));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>
    <InterviewChat projectId="project" runId="r" journey={journey} onCite={vi.fn()} />
  </QueryClientProvider>);
  return client;
}

function ask() {
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Why?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}


const imeCases = ["왜 샀나요?", "为什么购买？", "なぜ買いましたか？", "Why buy it?", "¿Por qué lo compraste?", "Pourquoi cet achat ?"]
  .flatMap(text => [{ text, flags: { isComposing: true } }, { text, flags: { keyCode: 229 } }]);
it.each(imeCases)("keeps composing text instead of sending an interview: $text $flags", async ({ text, flags }) => {
  vi.mocked(getInterview).mockResolvedValue(empty);
  vi.mocked(askShopper).mockImplementation(() => new Promise(() => {}));
  mount(); const input = screen.getByRole("textbox");
  fireEvent.change(input, { target: { value: text } });
  const allowed = fireEvent.keyDown(input, { key: "Enter", ...flags });
  await act(async () => {});
  expect(askShopper).not.toHaveBeenCalled(); expect((input as HTMLTextAreaElement).value).toBe(text); expect(allowed).toBe(true);
});

it("still sends on a normal Enter after composition ends", async () => {
  vi.mocked(getInterview).mockResolvedValue(empty); vi.mocked(askShopper).mockResolvedValue(answered); mount();
  const input = screen.getByRole("textbox"); fireEvent.change(input, { target: { value: "왜 샀나요?" } });
  expect(fireEvent.keyDown(input, { key: "Enter" })).toBe(false);
  await waitFor(() => expect(askShopper).toHaveBeenCalledWith("project", "r", "p", "왜 샀나요?", ""));
});

it("leaves Shift Enter available for a new line", async () => {
  vi.mocked(getInterview).mockResolvedValue(empty); vi.mocked(askShopper).mockImplementation(() => new Promise(() => {})); mount();
  const input = screen.getByRole("textbox"); fireEvent.change(input, { target: { value: "Why?" } });
  expect(fireEvent.keyDown(input, { key: "Enter", shiftKey: true })).toBe(true);
  await act(async () => {}); expect(askShopper).not.toHaveBeenCalled();
});

it("restores a failed question so it can be corrected or retried", async () => {
  vi.mocked(getInterview).mockResolvedValue(empty); vi.mocked(askShopper).mockRejectedValue(new Error("Temporary answer failure")); mount(); ask();
  await screen.findByText("Temporary answer failure"); expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("Why?");
  vi.mocked(askShopper).mockResolvedValue(answered); fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText("I was in a hurry."); expect(askShopper).toHaveBeenCalledTimes(2);
});

it("keeps a newly typed question when the previous question fails late", async () => {
  let reject!: (error: Error) => void; vi.mocked(getInterview).mockResolvedValue(empty);
  vi.mocked(askShopper).mockImplementation(() => new Promise((_resolve, fail) => { reject = fail; })); mount(); ask();
  await waitFor(() => expect(askShopper).toHaveBeenCalled()); fireEvent.change(screen.getByRole("textbox"), { target: { value: "A newer draft?" } });
  await act(async () => reject(new Error("Previous question failed")));
  await screen.findByText("Previous question failed"); expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("A newer draft?");
});
