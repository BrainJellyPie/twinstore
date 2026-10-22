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

it("refreshes the provider badge after a failed test and shows the whole message", async () => {
  const ready = { ...openai, has_key: true, key_source: "settings" as const, key_hint: "…abcd", ready: true };
  vi.mocked(api.getProviders).mockResolvedValue([ready]);
  const message = "OpenAI turned this key down: it is not valid or was revoked. Paste a new key in the field above, then test again.";
  vi.mocked(api.testModel).mockImplementation(async () => {
    vi.mocked(api.getProviders).mockResolvedValue([{ ...ready, key_rejected: true }]);
    return { ok: false, model: "gpt-mini", latency_ms: 0, reply: "", error: message, vision: false };
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ProvidersPanel /></QueryClientProvider>);
  expect(await screen.findByText("Ready")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Test" }));
  expect(await screen.findByText("Key turned down")).toBeTruthy();
  expect(screen.queryByText("Ready")).toBeNull();
  const result = screen.getByTestId("provider-test-result");
  expect(result.textContent).toBe(message);
  expect(result.querySelector(".truncate")).toBeNull();
  client.clear();
});

it("says a local server is not running when nothing answers at its saved address", async () => {
  const llama: api.ProviderStatus = {
    preset: { kind: "llamacpp", label: "llama.cpp", default_api_base: "http://127.0.0.1:8081/v1", api_key_env: null, needs_key: false, local: true,
      models: [{ id: "local", label: "Local", vision: true, note: "" }], docs_url: "" },
    enabled: true, has_key: false, key_source: "not needed", key_hint: "", api_base: "http://127.0.0.1:53303/v1", default_model: null,
    ready: true, answers: false,
  };
  vi.mocked(api.getProviders).mockResolvedValue([llama]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ProvidersPanel /></QueryClientProvider>);
  expect(await screen.findByText("Not running")).toBeTruthy();
  expect(screen.queryByText("Ready")).toBeNull();
  client.clear();
});
