// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { CreateStoreWizard } from "../components/CreateStoreWizard";

vi.mock("@tanstack/react-router", () => ({ useBlocker: () => ({ status: "idle" }) }));
vi.mock("@/shared/api/client", () => ({ createStore: vi.fn() }));
vi.mock("@/features/layouts/components/TemplatePicker", () => ({ TemplatePicker: () => null }));
const response = { metadata: { project_id: "new_project" }, setup: { id: "new_setup" }, personaGenId: "new_generation" } as api.CreateStoreResponse;
const clients: QueryClient[] = [];
beforeEach(() => { useLocale.getState().setLocale("en"); vi.mocked(api.createStore).mockResolvedValue(response); });
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); clients.push(client);
  const onCreated = vi.fn();
  const view = render(<QueryClientProvider client={client}><CreateStoreWizard onCreated={onCreated} /></QueryClientProvider>);
  return { ...view, onCreated };
}
async function generate() {
  fireEvent.change(screen.getByLabelText("Store name"), { target: { value: "Pending store" } });
  fireEvent.change(screen.getByLabelText("Address"), { target: { value: "12 Market Street" } });
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.change(screen.getByLabelText("Customer profile & behavior"), { target: { value: "Local residents" } });
  fireEvent.click(screen.getByRole("button", { name: "Create new store" }));
  fireEvent.click(await screen.findByRole("button", { name: "Generate" }));
}

it("disables edits and repeat requests while generation is starting", async () => {
  let resolve!: (response: api.CreateStoreResponse) => void;
  vi.mocked(api.createStore).mockReturnValue(new Promise((done) => { resolve = done; }));
  const { onCreated } = show(); await generate();
  const pending = await screen.findByRole("button", { name: "Creating store…" });
  expect((pending as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Back" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).disabled).toBe(true);
  fireEvent.click(pending); expect(api.createStore).toHaveBeenCalledOnce();
  expect(onCreated).not.toHaveBeenCalled();
  await act(async () => resolve(response));
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith("new_project"));
});

it("does not redirect back into the wizard's result after the user leaves", async () => {
  let resolve!: (response: api.CreateStoreResponse) => void;
  vi.mocked(api.createStore).mockReturnValue(new Promise((done) => { resolve = done; }));
  const { unmount, onCreated } = show(); await generate();
  await screen.findByRole("button", { name: "Creating store…" });
  unmount();
  await act(async () => resolve(response));
  expect(onCreated).not.toHaveBeenCalled();
});

it("preserves form data and makes a failed request retryable", async () => {
  vi.mocked(api.createStore).mockRejectedValueOnce(new Error("Store creation unavailable"));
  const { onCreated } = show(); await generate();
  expect((await screen.findByRole("alert")).textContent).toBe("Store creation unavailable");
  expect((screen.getByLabelText("Customer profile & behavior") as HTMLTextAreaElement).value).toBe("Local residents");
  fireEvent.click(screen.getByRole("button", { name: "Create new store" }));
  expect(screen.getByRole("alertdialog").textContent).toContain("Pending store");
  fireEvent.click(screen.getByRole("button", { name: "Generate" }));
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith("new_project"));
  expect(api.createStore).toHaveBeenCalledTimes(2);
});
