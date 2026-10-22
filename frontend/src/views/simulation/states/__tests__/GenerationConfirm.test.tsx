// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { useLocale } from "@/shared/i18n/i18n";
import { useSetupGeneration } from "@/shared/queries/useSetupGeneration";
import type { GenerationConfirm, GenerationListItem, GenerationStatus } from "@/shared/types/domain";
import { PreparingView } from "../PreparingView";
vi.mock("@/features/settings/useModelSetup", () => import("@/features/settings/__tests__/modelSetupWithKey"));

vi.mock("@/shared/api/client", () => ({
  getSetupGenerations: vi.fn(), getGenerationStatus: vi.fn(), regeneratePersona: vi.fn(), confirmGeneration: vi.fn(),
}));

const confirm: GenerationConfirm = {
  model: "anthropic/claude-haiku-5-5", local: false, days: 7,
  visitors_per_day: { "1": 480, "2": 500, "3": 500, "4": 520, "5": 540, "6": 560, "7": 540 },
  all: { per_day: 520, customers: 3640, requests: 182, minutes: 25, cost_usd: 1.8 },
  sample: { per_day: 20, customers: 140, requests: 7, minutes: 2, cost_usd: 0.004 },
};
const job = (patch: Partial<GenerationListItem> = {}): GenerationListItem => ({
  gen_id: "gen", setup_id: "s", kind: "persona", status: "running", error: null, progress: { confirm }, created_at: null, updated_at: null, ...patch,
});
const status = (patch: Partial<GenerationStatus> = {}): GenerationStatus => {
  const { gen_id: _id, ...rest } = job(patch);
  return rest;
};

function Harness() {
  const generation = useSetupGeneration("p", "s");
  return <PreparingView generation={generation} contextKind="persona" projectName="Corner store" layouts={[{ id: "s", name: "Floor" }]}
    selectedSetupId="s" onLayoutSelect={vi.fn()} onBackToStores={vi.fn()} onOpenSettings={vi.fn()} onAbandonProject={vi.fn()} />;
}
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  render(<Harness />, { wrapper });
}
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (error: Error) => void; const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; }); return { promise, resolve, reject }; }

beforeEach(() => {
  vi.mocked(api.getSetupGenerations).mockResolvedValue([job()]);
  vi.mocked(api.getGenerationStatus).mockResolvedValue(status());
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); });

it("says how many visitors a day were estimated and what each choice takes", async () => {
  show();
  const dialog = await screen.findByRole("alertdialog", { name: "How many customers should the model write?" });
  expect(dialog.textContent).toContain("The model estimated 480–560 visitors a day for this store, on 7 open days.");
  expect(dialog.textContent).toContain("anthropic/claude-haiku-5-5");
  const all = within(dialog).getByRole("button", { name: /Write all 3,640 customers/ });
  expect(all.textContent).toContain("182 model calls · about 25 min · about $1.80");
  const sample = within(dialog).getByRole("button", { name: /Quick sample: 20 a day/ });
  expect(sample.textContent).toContain("140 customers written; the rest of each day are copies of these customers.");
  expect(sample.textContent).toContain("7 model calls · about 2 min · < $0.01");
  expect(within(dialog).getByRole("button", { name: "Cancel" })).toBeTruthy();
});

it("says a local model is free, an unpriced cloud model's cost is unknown, and one estimate a day plainly", async () => {
  vi.mocked(api.getSetupGenerations).mockResolvedValue([job({ progress: { confirm: { ...confirm, local: true, model: "llamacpp/qwen3.5-0.8b" } } })]);
  vi.mocked(api.getGenerationStatus).mockResolvedValue(status({ progress: { confirm: { ...confirm, local: true, model: "llamacpp/qwen3.5-0.8b" } } }));
  show();
  const dialog = await screen.findByRole("alertdialog");
  expect(within(dialog).getByRole("button", { name: /Write all/ }).textContent).toContain("free on this computer");
  cleanup();
  const flat = { ...confirm, visitors_per_day: { "1": 300, "2": 300 }, days: 2, all: { ...confirm.all, cost_usd: null } };
  vi.mocked(api.getSetupGenerations).mockResolvedValue([job({ progress: { confirm: flat } })]);
  vi.mocked(api.getGenerationStatus).mockResolvedValue(status({ progress: { confirm: flat } }));
  show();
  const again = await screen.findByRole("alertdialog");
  expect(again.textContent).toContain("about 300 visitors a day for this store, on 2 open days");
  expect(within(again).getByRole("button", { name: /Write all/ }).textContent).toContain("cost unknown");
});

it("posts the choice once and disables the buttons while it is sent", async () => {
  const sent = deferred<GenerationStatus>();
  vi.mocked(api.confirmGeneration).mockReturnValue(sent.promise);
  show();
  const dialog = await screen.findByRole("alertdialog");
  await waitFor(() => expect(api.getGenerationStatus).toHaveBeenCalled());
  fireEvent.click(within(dialog).getByRole("button", { name: /Quick sample/ }));
  fireEvent.click(within(dialog).getByRole("button", { name: /Write all/ }));
  expect(api.confirmGeneration).toHaveBeenCalledOnce();
  expect(api.confirmGeneration).toHaveBeenCalledWith("p", "s", "gen", "sample");
  for (const button of within(dialog).getAllByRole("button")) expect((button as HTMLButtonElement).disabled).toBe(true);
  await act(async () => sent.resolve(status({ progress: { note: "Writing the customers…" } })));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  // The answer's note is not a wait for the local model.
  expect(screen.queryByText(/No model API key works right now/)).toBeNull();
  expect(screen.getByRole("heading", { name: "Generating customers…" })).toBeTruthy();
});

it("cancels with the explicit button and keeps the dialog open on Escape", async () => {
  vi.mocked(api.confirmGeneration).mockResolvedValue(status({ status: "failed", progress: null, error: "You canceled writing the customers. Use Try again." }));
  show();
  const dialog = await screen.findByRole("alertdialog");
  await waitFor(() => expect(api.getGenerationStatus).toHaveBeenCalled());
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(screen.getByRole("alertdialog")).toBeTruthy();
  expect(api.confirmGeneration).not.toHaveBeenCalled();
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(api.confirmGeneration).toHaveBeenCalledWith("p", "s", "gen", "cancel");
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(screen.getByRole("heading", { name: "Customer generation failed" })).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain("You canceled writing the customers");
  expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
});

it("refreshes the status when the job is no longer waiting (409)", async () => {
  vi.mocked(api.confirmGeneration).mockRejectedValue(new ApiError("This generation is not waiting for a choice.", 409));
  show();
  const dialog = await screen.findByRole("alertdialog");
  await waitFor(() => expect(api.getGenerationStatus).toHaveBeenCalledOnce());
  vi.mocked(api.getGenerationStatus).mockResolvedValue(status({ progress: { written: 300, total: 3640 } }));
  fireEvent.click(within(dialog).getByRole("button", { name: /Write all/ }));
  await waitFor(() => expect(api.getGenerationStatus).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(await screen.findByText("Writing customers: 300 of 3,640")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("shows a failed answer and lets the user choose again", async () => {
  vi.mocked(api.confirmGeneration).mockRejectedValueOnce(new Error("Server unavailable")).mockResolvedValueOnce(status({ progress: { written: 20, total: 140 } }));
  show();
  const dialog = await screen.findByRole("alertdialog");
  await waitFor(() => expect(api.getGenerationStatus).toHaveBeenCalled());
  fireEvent.click(within(dialog).getByRole("button", { name: /Quick sample/ }));
  const alert = await within(dialog).findByRole("alert");
  expect(alert.textContent).toContain("Could not send your choice. Try again.");
  expect(alert.textContent).toContain("Server unavailable");
  const sample = within(dialog).getByRole("button", { name: /Quick sample/ }) as HTMLButtonElement;
  expect(sample.disabled).toBe(false);
  fireEvent.click(sample);
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(api.confirmGeneration).toHaveBeenCalledTimes(2);
  expect(screen.getByText("Writing customers: 20 of 140")).toBeTruthy();
});

it("asks in Korean", async () => {
  useLocale.getState().setLocale("ko");
  show();
  const dialog = await screen.findByRole("alertdialog", { name: "모델이 고객을 몇 명 작성할까요?" });
  expect(dialog.textContent).toContain("이 매장의 예상 방문객은 하루 480~560명이고, 영업일은 7일입니다.");
  expect(within(dialog).getByRole("button", { name: /고객 3,640명 모두 작성/ }).textContent).toContain("약 25분 · 약 $1.80");
  expect(within(dialog).getByRole("button", { name: /빠른 표본: 하루 20명/ })).toBeTruthy();
  expect(within(dialog).getByRole("button", { name: "취소" })).toBeTruthy();
});
