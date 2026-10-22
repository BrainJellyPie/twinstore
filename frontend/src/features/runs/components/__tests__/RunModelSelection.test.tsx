// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { useLocale, translate } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import { RunLauncherDialog } from "../RunLauncherDialog";

vi.mock("@/shared/api/client", () => ({ getEngines: vi.fn(), getTown: vi.fn(), getScenarios: vi.fn(), getModels: vi.fn(), startRun: vi.fn(), estimateRun: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ Link: ({ to, children, ...props }: { to: string; children: ReactNode }) => <a href={to} {...props}>{children}</a> }));
const models: api.ModelOption[] = [
  { ref: "provider:text", provider: "A", label: "Text model", vision: false, local: false },
  { ref: "provider:vision", provider: "A", label: "Vision model", vision: true, local: false },
  { ref: "other:vision", provider: "B", label: "Other vision", vision: true, local: true },
];
const clients: QueryClient[] = [];
const quick: api.RunEstimate = { customers: 1000, days: 7, per_day: 143, engine: "rule_based", model: "", local: false, model_calls: 0, minutes: 1, cost_usd: null, warn: false };
beforeEach(() => {
  vi.mocked(api.estimateRun).mockResolvedValue(quick);
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(api.getEngines).mockResolvedValue([]);
  vi.mocked(api.getTown).mockResolvedValue(null);
  vi.mocked(api.getScenarios).mockResolvedValue([]);
  vi.mocked(api.getModels).mockResolvedValue(models);
  vi.mocked(api.startRun).mockResolvedValue({ project_id: "p", setup_id: "s", run_id: "r" });
});
afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); vi.unstubAllGlobals(); });
function show(engine: api.EngineType = "pattern_intent_impulse") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}><RunLauncherDialog open onOpenChange={() => {}} projectId="p" setupId="s" personaCount={1000} defaultEngine={engine} /></QueryClientProvider>);
  const details = document.querySelector("details")!; details.open = true;
  return client;
}
async function submit() { await act(async () => { fireEvent.submit(document.querySelector("form")!); }); }

it("does not silently use the default after choosing one model before the list arrives", async () => {
  let resolve!: (models: api.ModelOption[]) => void;
  vi.mocked(api.getModels).mockReturnValue(new Promise((done) => { resolve = done; }));
  show(); fireEvent.click(screen.getByText("One model", { selector: "button" }));
  await act(async () => resolve(models));
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Model" })).toBeTruthy());
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
});

it("does not silently use the default for an empty ensemble", async () => {
  show(); await waitFor(() => expect(api.getModels).toHaveBeenCalled());
  fireEvent.click(screen.getByText("Ensemble", { selector: "button" }));
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
});

it("does not silently use the default when there are no connected models", async () => {
  vi.mocked(api.getModels).mockResolvedValue([]);
  show(); fireEvent.click(screen.getByText("One model", { selector: "button" }));
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
});

it("sends the explicitly selected model", async () => {
  show(); await waitFor(() => expect(api.getModels).toHaveBeenCalled());
  fireEvent.click(screen.getByText("One model", { selector: "button" }));
  const select = await screen.findByRole("combobox", { name: "Model" });
  fireEvent.change(select, { target: { value: "other:vision" } });
  await submit(); expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ model: "other:vision" }));
});

it("keeps the server default available while the catalog is still loading", async () => {
  vi.mocked(api.getModels).mockReturnValue(new Promise(() => {}));
  show(); await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ model: undefined, ensemble: undefined }));
});

it("allows the server default after a catalog failure", async () => {
  vi.mocked(api.getModels).mockRejectedValue(new Error("Catalog offline"));
  show(); expect((await screen.findByRole("alert")).textContent).toContain("Catalog offline");
  await submit(); expect(api.startRun).toHaveBeenCalledOnce();
});

it("retries a failed catalog without changing an incomplete single-model choice", async () => {
  vi.mocked(api.getModels).mockRejectedValueOnce(new Error("Catalog offline"));
  show(); await screen.findByRole("alert");
  fireEvent.click(screen.getByText("One model", { selector: "button" }));
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Retry models" }));
  await waitFor(() => expect((screen.getByRole("combobox", { name: "Model" }) as HTMLSelectElement).disabled).toBe(false));
  const select = screen.getByRole("combobox", { name: "Model" });
  expect((select as HTMLSelectElement).value).toBe("");
  fireEvent.change(select, { target: { value: "provider:vision" } });
  await submit(); expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ model: "provider:vision" }));
});

it("shows a removed selection honestly and lets the user choose another model", async () => {
  const client = show(); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  fireEvent.click(screen.getByText("One model", { selector: "button" }));
  const select = screen.getByRole("combobox", { name: "Model" });
  fireEvent.change(select, { target: { value: "other:vision" } });
  await act(async () => { client.setQueryData(queryKeys.models(), [models[0]!]); });
  await screen.findByText("Unavailable model: other:vision", { selector: "p" });
  expect((select as HTMLSelectElement).value).toBe("other:vision");
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
  fireEvent.change(select, { target: { value: "provider:text" } });
  await submit(); expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ model: "provider:text" }));
});

it("retains a known selection after a background catalog refresh fails", async () => {
  const client = show(); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  fireEvent.click(screen.getByText("One model", { selector: "button" }));
  vi.mocked(api.getModels).mockRejectedValueOnce(new Error("Refresh offline"));
  await act(async () => { await client.invalidateQueries({ queryKey: queryKeys.models() }); });
  await screen.findByText("Refresh offline");
  await submit(); expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ model: "provider:text" }));
});

it("builds an ensemble with one usable model per provider", async () => {
  const client = show(); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  fireEvent.click(screen.getByText("Ensemble", { selector: "button" }));
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  expect((screen.getByLabelText("Weight of Text model") as HTMLInputElement).checkValidity()).toBe(true);
  expect((screen.getByLabelText("Weight of Other vision") as HTMLInputElement).checkValidity()).toBe(true);
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ ensemble: { mode: "mixture", members: [{ model: "provider:text", weight: 1 }, { model: "other:vision", weight: 1 }] } }));
});

it("only offers vision-capable models to vision shoppers and preserves vote mode", async () => {
  const client = show("vlm_glance"); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  fireEvent.click(screen.getByText("One model", { selector: "button" }));
  expect(screen.queryByRole("option", { name: /Text model/ })).toBeNull();
  fireEvent.click(screen.getByText("Ensemble", { selector: "button" }));
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  fireEvent.click(screen.getByRole("radio", { name: /^Vote / }));
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ ensemble: { mode: "vote", members: [{ model: "provider:vision", weight: 1 }, { model: "other:vision", weight: 1 }] } }));
});

it.each(LOCALES)("explains an empty ensemble in $code and allows a deliberate default", async ({ code }) => {
  useLocale.getState().setLocale(code);
  const client = show(); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  fireEvent.click(screen.getByRole("button", { name: translate(code, "ensemble") }));
  expect(screen.getByRole("alert").textContent).toBe(translate(code, "needEnsemble"));
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "serverDefault") }));
  await submit(); expect(api.startRun).toHaveBeenCalledOnce();
});

it("lets the user remove an unavailable ensemble member without discarding the others", async () => {
  const client = show(); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  fireEvent.click(screen.getByText("Ensemble", { selector: "button" }));
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  await act(async () => { client.setQueryData(queryKeys.models(), [models[0]!]); });
  await screen.findByText(/An ensemble model is unavailable/);
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Remove other:vision" }));
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ ensemble: { mode: "mixture", members: [{ model: "provider:text", weight: 1 }] } }));
});

it.each(["0.001", "0.01", "0.1", "0.25", "1", "1.5", "2.75"])("accepts the positive ensemble weight %s in native form validation", async (weight) => {
  const client = show(); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  fireEvent.click(screen.getByText("Ensemble", { selector: "button" }));
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  const input = screen.getByLabelText("Weight of Text model") as HTMLInputElement;
  fireEvent.change(input, { target: { value: weight } });
  expect(input.checkValidity()).toBe(true);
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ ensemble: { mode: "mixture", members: [{ model: "provider:text", weight: Number(weight) }, { model: "other:vision", weight: 1 }] } }));
});

it("can remove every unavailable ensemble member and deliberately return to the default", async () => {
  const client = show(); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  fireEvent.click(screen.getByText("Ensemble", { selector: "button" }));
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  await act(async () => { client.setQueryData(queryKeys.models(), []); });
  fireEvent.click(await screen.findByRole("button", { name: "Remove provider:text" }));
  fireEvent.click(screen.getByRole("button", { name: "Remove other:vision" }));
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
  expect(screen.getByRole("alert").textContent).toBe("Select at least one ensemble model in Advanced settings.");
  fireEvent.click(screen.getByText("Server default", { selector: "button" }));
  await submit(); expect(api.startRun).toHaveBeenCalledOnce();
});

it("does not offer a text-only catalog to vision shoppers as a valid model choice", async () => {
  vi.mocked(api.getModels).mockResolvedValue([models[0]!]);
  const client = show("vlm_glance"); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual([models[0]!]));
  fireEvent.click(screen.getByText("One model", { selector: "button" }));
  expect((screen.getByRole("combobox", { name: "Model" }) as HTMLSelectElement).disabled).toBe(true);
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
});

it.each(["", "0", "-1"])("keeps an incomplete or invalid weight (%j) editable and blocks execution", async (weight) => {
  const client = show(); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  fireEvent.click(screen.getByText("Ensemble", { selector: "button" }));
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  const input = screen.getByLabelText("Weight of Text model") as HTMLInputElement;
  fireEvent.change(input, { target: { value: weight } });
  expect(input.value).toBe(weight);
  await submit(); expect(api.startRun).not.toHaveBeenCalled();
  fireEvent.change(input, { target: { value: "0.25" } });
  await submit();
  expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ ensemble: { mode: "mixture", members: [{ model: "provider:text", weight: 0.25 }, { model: "other:vision", weight: 1 }] } }));
});

it("keeps raw weight edits when the selected mode button is pressed again", async () => {
  const client = show(); await waitFor(() => expect(client.getQueryData(queryKeys.models())).toEqual(models));
  const ensemble = screen.getByText("Ensemble", { selector: "button" });
  fireEvent.click(ensemble);
  fireEvent.click(screen.getByRole("button", { name: "Mix one model from each provider" }));
  const input = screen.getByLabelText("Weight of Text model") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "1e0" } });
  fireEvent.click(ensemble);
  expect(input.value).toBe("1e0");
  await submit(); expect(api.startRun).toHaveBeenCalledWith("p", "s", expect.objectContaining({ ensemble: { mode: "mixture", members: [{ model: "provider:text", weight: 1 }, { model: "other:vision", weight: 1 }] } }));
});
