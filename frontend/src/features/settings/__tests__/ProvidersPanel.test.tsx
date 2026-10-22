// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { queryKeys } from "@/shared/queries/keys";
import { ProvidersPanel } from "../ProvidersPanel";

vi.mock("@/shared/api/client", () => ({ getProviders: vi.fn(), updateProvider: vi.fn(), testModel: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const openai: api.ProviderStatus = {
  preset: { kind: "openai", label: "OpenAI", default_api_base: null, api_key_env: "OPENAI_API_KEY", needs_key: true, local: false, models: [{ id: "gpt-mini", label: "Mini", vision: true, note: "" }], docs_url: "" },
  enabled: true, has_key: false, key_source: "none", key_hint: "", api_base: null, default_model: null, ready: false,
};

it("refreshes the run dialog's engine readiness after an API key is saved", async () => {
  vi.mocked(api.getProviders).mockResolvedValue([openai]);
  vi.mocked(api.updateProvider).mockResolvedValue({ ...openai, has_key: true, key_source: "settings", ready: true });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><ProvidersPanel /></QueryClientProvider>);
  fireEvent.change(await screen.findByLabelText("OpenAI API key"), { target: { value: " sk-test " } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.engines() }));
  expect(api.updateProvider).toHaveBeenCalledWith("openai", { api_key: "sk-test" });
  client.clear();
});

it("shows a rejected key save on the card and keeps the typed key", async () => {
  vi.mocked(api.getProviders).mockResolvedValue([openai]);
  vi.mocked(api.updateProvider).mockRejectedValue(new ApiError("The key format is not valid for OpenAI.", 400));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ProvidersPanel /></QueryClientProvider>);
  const input = await screen.findByLabelText("OpenAI API key") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "bad" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect((await screen.findByRole("alert")).textContent).toBe("The key format is not valid for OpenAI.");
  expect(input.value).toBe("bad");
  client.clear();
});

it("shows a failed connection test without the error class name", async () => {
  vi.mocked(api.getProviders).mockResolvedValue([{ ...openai, has_key: true, key_source: "settings", ready: true }]);
  vi.mocked(api.testModel).mockRejectedValue(new ApiError("Model gpt-mini is not available", 404));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ProvidersPanel /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Test" }));
  expect(await screen.findByText("Model gpt-mini is not available")).toBeTruthy();
  expect(screen.queryByText(/ApiError/)).toBeNull();
  client.clear();
});
