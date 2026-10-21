// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { designSurvey, startSurvey, type SurveyDesign } from "@/shared/api/marketing";
import { SurveyBuilder } from "../SurveyBuilder";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), startSurvey: vi.fn(), designSurvey: vi.fn(),
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [{ asset_id: "gold", name: "Label Gold" }, { asset_id: "leaf", name: "Label Leaf" }] }) }));
vi.mock("../ProductLibrary", () => ({ ProductDrop: () => null }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const DESIGN: SurveyDesign = {
  name: "Premium labels", stimuli: ["gold", "leaf"], stimulus_names: ["Gold", "Leaf"], questions: ["appeal", "preference", "open"],
  context: "A new bottled green tea, 500 ml.", reference_price: 199, currency: "USD", age_groups: ["20s"], genders: [],
  rationale: "Twenties compare two labels.", warnings: ['No product image "Label Moon" in the library; it was left out.'],
};

function mount(props: Partial<Parameters<typeof SurveyBuilder>[0]> = {}) {
  const started = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}>
    <SurveyBuilder projectId="p" personaCount={60} defaultCurrency="USD" setupId="s1" onStarted={started} {...props} />
  </QueryClientProvider>);
  return started;
}

it("drafts the test from a question and fields it as drafted", async () => {
  vi.mocked(designSurvey).mockResolvedValue(DESIGN);
  vi.mocked(startSurvey).mockResolvedValue({ job_id: "srv", kind: "survey", name: "", status: "pending", stage: "", progress: 0, error: "", created_at: "", finished_at: "" });
  const started = mount();
  fireEvent.change(screen.getByLabelText("Question for the concept test"), { target: { value: "Which label looks more premium to people in their twenties?" } });
  fireEvent.click(screen.getByRole("button", { name: "Draft the test" }));
  expect(await screen.findByText(/Twenties compare two labels\./)).toBeTruthy();
  expect(designSurvey).toHaveBeenCalledWith("p", { question: "Which label looks more premium to people in their twenties?", setup_id: "s1", currency: "USD" });
  expect(screen.getByText(/Label Moon/)).toBeTruthy();
  expect((screen.getByLabelText("Name of A") as HTMLInputElement).value).toBe("Gold");
  expect((screen.getByLabelText("Shelf price shown with A (optional)") as HTMLInputElement).value).toBe("1.99");
  fireEvent.click(screen.getByRole("button", { name: "Field the survey" }));
  await waitFor(() => expect(started).toHaveBeenCalled());
  expect(startSurvey).toHaveBeenCalledWith("p", expect.objectContaining({
    name: "Premium labels", stimuli: ["gold", "leaf"], stimulus_names: ["Gold", "Leaf"], questions: ["appeal", "preference", "open"],
    context: "A new bottled green tea, 500 ml.", reference_price: 199, age_groups: ["20s"], genders: [],
  }));
});

it("drafts once from a request routed by the command palette", async () => {
  vi.mocked(designSurvey).mockResolvedValue(DESIGN);
  mount({ prefill: { id: 4, text: "Which label looks more premium?" } });
  expect(await screen.findByText(/Twenties compare two labels\./)).toBeTruthy();
  expect((screen.getByLabelText("Question for the concept test") as HTMLInputElement).value).toBe("Which label looks more premium?");
  expect(designSurvey).toHaveBeenCalledTimes(1);
});
