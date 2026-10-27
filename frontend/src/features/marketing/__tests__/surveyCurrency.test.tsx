// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { startSurvey } from "@/shared/api/marketing";
import { useLocale } from "@/shared/i18n/i18n";
import { SurveyBuilder } from "../SurveyBuilder";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), startSurvey: vi.fn(),
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [{ asset_id: "tea", name: "Tea" }] }) }));
vi.mock("../ProductLibrary", () => ({ ProductDrop: () => null }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it.each(["KRW", "JPY"])("uses the project's %s currency for a new survey and its reference price", async (currency) => {
  vi.mocked(startSurvey).mockResolvedValue({ job_id: "srv_test", kind: "survey", name: "Test", status: "pending",
    stage: "queued", progress: 0, error: "", created_at: "", finished_at: "" });
  const started = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}>
    <SurveyBuilder projectId="project" personaCount={60} defaultCurrency={currency} onStarted={started} />
  </QueryClientProvider>);
  expect((screen.getByRole("combobox", { name: "Currency" }) as HTMLSelectElement).value).toBe(currency);
  fireEvent.click(screen.getByTitle("Tea"));
  fireEvent.change(screen.getByLabelText("Shelf price shown with A (optional)"), { target: { value: "2500" } });
  fireEvent.click(screen.getByRole("button", { name: "Field the survey" }));

  await waitFor(() => expect(started).toHaveBeenCalled());
  expect(startSurvey).toHaveBeenCalledWith("project", expect.objectContaining({ currency, reference_price: 2500 }));
});

it("tells assistive technology which library pack is picked", () => {
  render(<QueryClientProvider client={new QueryClient()}>
    <SurveyBuilder projectId="project" personaCount={60} defaultCurrency="USD" onStarted={vi.fn()} />
  </QueryClientProvider>);
  const tea = screen.getByRole("button", { name: "Tea" });
  expect(tea.getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(tea);
  expect(tea.getAttribute("aria-pressed")).toBe("true");
});

it("says what the survey still needs until a pack is picked", () => {
  render(<QueryClientProvider client={new QueryClient()}>
    <SurveyBuilder projectId="project" personaCount={60} defaultCurrency="USD" onStarted={vi.fn()} />
  </QueryClientProvider>);
  const needs = "To field the survey, pick at least one pack and one question.";
  expect(screen.getByText(needs)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Tea" }));
  expect(screen.queryByText(needs)).toBeNull();
});

it("shows the example shelf price with the selected language's decimal separator", () => {
  useLocale.getState().setLocale("fr");
  try {
    render(<QueryClientProvider client={new QueryClient()}>
      <SurveyBuilder projectId="project" personaCount={60} defaultCurrency="EUR" onStarted={vi.fn()} />
    </QueryClientProvider>);
    expect(screen.getByLabelText("Prix en rayon affiché avec A (facultatif)").getAttribute("placeholder")).toBe("1,99");
  } finally {
    useLocale.getState().setLocale("en");
  }
});
