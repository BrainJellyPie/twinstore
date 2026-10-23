// @vitest-environment jsdom
import type { ReactNode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { LOCALES } from "@/shared/i18n/messages";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { NeedsModel } from "../NeedsModel";
import { setupWithKey } from "./modelSetupWithKey";

vi.mock("@/shared/api/client", async original => ({ ...await original<typeof import("@/shared/api/client")>(), getModelSetup: vi.fn(), startLocalModel: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ Link: ({ to, children }: { to: string; children: ReactNode }) => <a href={to}>{children}</a> }));
const noKey: api.ModelSetup = { ...setupWithKey, cloud_providers: [], local: { ...setupWithKey.local, state: "off", downloaded: false } };
let client: QueryClient;
beforeEach(() => { client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); });
afterEach(() => { cleanup(); client.clear(); useLocale.getState().setLocale("en"); vi.resetAllMocks(); });
function mount(setup: api.ModelSetup) {
  vi.mocked(api.getModelSetup).mockResolvedValue(setup);
  render(<QueryClientProvider client={client}><NeedsModel /></QueryClientProvider>);
}

it.each(LOCALES)("explains a disabled local model without offering a download in $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  mount({ ...noKey, local: { ...noKey.local, state: "disabled" } });
  await screen.findByText(translate(code, "needsModelDisabledHint"));
  expect(screen.queryByText(translate(code, "needsModelHint"))).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
  expect(screen.getByRole("link", { name: translate(code, "modelSettings") }).getAttribute("href")).toBe("/settings");
  expect(api.startLocalModel).not.toHaveBeenCalled();
});

it.each(LOCALES)("waits for an explicit download and localizes a late failure/retry after switching from $code", async ({ code }) => {
  useLocale.getState().setLocale(code);
  let reject!: (error: Error) => void;
  vi.mocked(api.startLocalModel).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
  mount(noKey);
  await screen.findByText(translate(code, "needsModelHint"));
  expect(api.startLocalModel).not.toHaveBeenCalled();
  const download = screen.getByRole("button", { name: translate(code, "downloadLocal", { size: 2 }) });
  fireEvent.click(download);
  await waitFor(() => expect(api.startLocalModel).toHaveBeenCalledOnce());
  expect(download.matches(":disabled")).toBe(true);
  const next = code === "fr" ? "ko" : "fr";
  act(() => useLocale.getState().setLocale(next));
  const pending = screen.getByRole("button", { name: translate(next, "downloadLocal", { size: 2 }) });
  expect(pending.matches(":disabled")).toBe(true); fireEvent.click(pending);
  expect(api.startLocalModel).toHaveBeenCalledOnce();
  const original = "Original download error <model> 茶 {size}";
  await act(async () => reject(new ApiError(original, 503)));
  expect(await screen.findByText(translate(next, "requestFailed"))).toBeTruthy();
  fireEvent.click(screen.getByText(translate(next, "requestDetails")));
  expect(screen.getByText(original)).toBeTruthy();
  expect(document.querySelector("model")).toBeNull();
  const starting = { ...noKey.local, state: "starting" as const };
  vi.mocked(api.startLocalModel).mockResolvedValue(starting);
  vi.mocked(api.getModelSetup).mockResolvedValue({ ...noKey, local: starting });
  fireEvent.click(screen.getByRole("button", { name: translate(next, "downloadLocal", { size: 2 }) }));
  await screen.findByText(translate(next, "localStateStarting"));
  expect(api.startLocalModel).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole("alert")).toBeNull();
});
