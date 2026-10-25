// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as online from "@/shared/api/online";
import type { AnalystThread } from "@/shared/api/interview";
import { useLocale } from "@/shared/i18n/i18n";
import { useAssistStore } from "@/stores/assistStore";
import { OnlineAnalyst } from "../OnlineAnalyst";

vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getModels: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({
  ...await original<typeof online>(), getOnlineAnalyst: vi.fn(), askOnlineAnalyst: vi.fn(), clearOnlineAnalyst: vi.fn(),
}));

const empty: AnalystThread = { run_id: "r", model: "", messages: [] };
const winner = "Did the variant really do better, or is the difference unclear?";
const answered: AnalystThread = { run_id: "r", model: "m", messages: [
  { role: "user", text: winner, figures: [], follow_ups: [], created_at: "" },
  { role: "analyst", text: "Conversion moved by 2 points but the interval includes zero.", created_at: "",
    figures: ["Quick add minus control (same shoppers, 95 % interval): conversion +2.0 pt [-1.0 pt, +5.0 pt]."],
    follow_ups: ["Which shoppers changed their mind?"] },
] };

beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(online.getOnlineAnalyst).mockResolvedValue(empty);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); useAssistStore.setState({ pending: null }); });

function mount(compared: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><OnlineAnalyst projectId="p1" runId="r" compared={compared} /></QueryClientProvider>);
}

it("asks a starter, shows the answer with the report lines it used, and offers its follow-ups", async () => {
  vi.mocked(online.askOnlineAnalyst).mockResolvedValue(answered);
  mount(true);
  fireEvent.click(await screen.findByRole("button", { name: winner }));
  expect(await screen.findByText("Conversion moved by 2 points but the interval includes zero.")).toBeTruthy();
  expect(online.askOnlineAnalyst).toHaveBeenCalledWith("p1", "r", winner, "");
  const used = screen.getByRole("list", { name: "Figures used" });
  expect(used.textContent).toContain("conversion +2.0 pt [-1.0 pt, +5.0 pt]");
  vi.mocked(online.askOnlineAnalyst).mockResolvedValue(answered);
  fireEvent.click(screen.getByRole("button", { name: "Which shoppers changed their mind?" }));
  await waitFor(() => expect(online.askOnlineAnalyst).toHaveBeenLastCalledWith("p1", "r", "Which shoppers changed their mind?", ""));
});

it("starts a one-store run with what holds sales back, and keeps a question that could not be answered", async () => {
  vi.mocked(online.askOnlineAnalyst).mockRejectedValue(new Error("502 Bad Gateway: rate limited"));
  mount(false);
  expect(await screen.findByRole("button", { name: "What holds sales back most on this store?" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: winner })).toBeNull();
  const box = screen.getByRole("textbox", { name: "Question about this run" }) as HTMLInputElement;
  fireEvent.change(box, { target: { value: "Why do phone shoppers buy less?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("The question could not be answered.");
  expect(alert.textContent).toContain("rate limited");
  await waitFor(() => expect(box.value).toBe("Why do phone shoppers buy less?"));
});

it("clears the thread", async () => {
  vi.mocked(online.getOnlineAnalyst).mockResolvedValue(answered);
  vi.mocked(online.clearOnlineAnalyst).mockResolvedValue(undefined);
  mount(true);
  fireEvent.click(await screen.findByRole("button", { name: "Clear" }));
  expect(await screen.findByRole("button", { name: winner })).toBeTruthy();
  expect(online.clearOnlineAnalyst).toHaveBeenCalledWith("p1", "r");
});

it("asks a question routed from the command palette as soon as the run is open", async () => {
  vi.mocked(online.askOnlineAnalyst).mockResolvedValue(answered);
  useAssistStore.getState().send({ projectId: "p1", destination: "online_question", text: "Did quick add help?" });
  mount(true);
  await waitFor(() => expect(online.askOnlineAnalyst).toHaveBeenCalledWith("p1", "r", "Did quick add help?", ""));
  expect(useAssistStore.getState().pending).toBeNull();
});
