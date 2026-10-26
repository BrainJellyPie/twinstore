// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { CreateStoreWizard } from "@/features/setup/components/CreateStoreWizard";
import { PreparingView } from "@/views/simulation/states/PreparingView";
import { NeedsModel } from "../NeedsModel";
import { modelAvailable } from "../useModelSetup";
import { setupWithKey } from "./modelSetupWithKey";

vi.mock("@/shared/api/client", async (original) => ({
  ...await original<typeof import("@/shared/api/client")>(), getModelSetup: vi.fn(), startLocalModel: vi.fn(),
}));
vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children }: { to: string; children: ReactNode }) => <a href={to}>{children}</a>,
  useBlocker: () => ({ status: "idle" }),
}));
vi.mock("@/shared/mutations/useCreateStore", () => ({ useCreateStore: () => ({ mutateAsync: vi.fn(), isPending: false, error: null }) }));

const noKey: api.ModelSetup = { ...setupWithKey, cloud_providers: [], local: { ...setupWithKey.local, downloaded: false } };
const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); });

async function show(setup: api.ModelSetup, ui: ReactNode = <NeedsModel />) {
  vi.mocked(api.getModelSetup).mockResolvedValue(setup);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
  await waitFor(() => expect(client.getQueryData(queryKeys.modelSetup())).toEqual(setup));
}

it("asks for a key or the local model's download, and downloads only on the click", async () => {
  vi.mocked(api.startLocalModel).mockResolvedValue({ ...noKey.local, state: "downloading" });
  await show(noKey);
  expect(screen.getByTestId("needs-model").textContent).toContain("Creating virtual customers requires a model");
  expect(screen.getByRole("link", { name: "Model settings" }).getAttribute("href")).toBe("/settings");
  expect(api.startLocalModel).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Download local model (2 GB)" }));
  await waitFor(() => expect(api.startLocalModel).toHaveBeenCalledOnce());
});

it("words the hint for a model helper such as the designer or an analyst", async () => {
  await show(noKey, <NeedsModel purpose="assist" />);
  expect(screen.getByTestId("needs-model").textContent).toContain("This needs a model.");
  expect(screen.getByTestId("needs-model").textContent).not.toContain("virtual customers");
  expect(screen.getByRole("link", { name: "Model settings" }).getAttribute("href")).toBe("/settings");
});

it("offers one settings action after customer generation fails and keeps local-model recovery", async () => {
  const onOpenSettings = vi.fn();
  vi.mocked(api.startLocalModel).mockResolvedValue({ ...noKey.local, state: "downloading" });
  await show(noKey, <PreparingView
    generation={{ phase: "failed", kind: "persona", currentGenId: "failed_customers", error: "No model key", retry: vi.fn(), retrying: false }}
    contextKind="persona" projectName="Photo shop" layouts={[]} selectedSetupId="floor"
    onLayoutSelect={vi.fn()} onBackToStores={vi.fn()} onOpenSettings={onOpenSettings} onAbandonProject={vi.fn()}
  />);
  expect(screen.queryByRole("link", { name: "Model settings" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Model settings" }));
  expect(onOpenSettings).toHaveBeenCalledOnce();
  expect(api.startLocalModel).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Download local model (2 GB)" }));
  await waitFor(() => expect(api.startLocalModel).toHaveBeenCalledOnce());
});

it("stays out of the way when a model answers or is on its way", async () => {
  await show(setupWithKey);
  expect(screen.queryByTestId("needs-model")).toBeNull();
  cleanup();
  await show({ ...noKey, local: { ...noKey.local, state: "ready" } });
  expect(screen.queryByTestId("needs-model")).toBeNull();
  cleanup();
  await show({ ...noKey, local: { ...noKey.local, state: "downloading", progress: 0.4 } });
  expect(screen.getByTestId("needs-model").textContent).toContain("40%");
  expect(screen.queryByRole("button", { name: /Download local model/ })).toBeNull();
});

it("tells model setups apart", () => {
  expect(modelAvailable(setupWithKey)).toBe(true);
  expect(modelAvailable(noKey)).toBe(false);
  expect(modelAvailable({ ...noKey, local: { ...noKey.local, state: "starting" } })).toBe(true);
});

it("new stores start from the format's own products when no model can choose them", async () => {
  await show(noKey, <CreateStoreWizard />);
  const option = screen.getByLabelText("Choose starter products for this store automatically") as HTMLInputElement;
  expect(option.checked).toBe(false);
  fireEvent.click(option);        // still the user's to choose
  expect((screen.getByLabelText("Choose starter products for this store automatically") as HTMLInputElement).checked).toBe(true);
});

it("new stores let a model choose the products when one is set up", async () => {
  await show(setupWithKey, <CreateStoreWizard />);
  expect((screen.getByLabelText("Choose starter products for this store automatically") as HTMLInputElement).checked).toBe(true);
});
