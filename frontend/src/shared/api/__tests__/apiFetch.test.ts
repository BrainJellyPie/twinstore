// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";

import { useLocale } from "@/shared/i18n/i18n";
import { UserMessageError } from "@/shared/i18n/userMessage";
import { apiFetch } from "../errors";

afterEach(() => { vi.unstubAllGlobals(); useLocale.getState().setLocale("en"); });

it("says the app's server cannot be reached, in the chosen language, instead of the browser's wording", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
  useLocale.getState().setLocale("fr");
  const error = await apiFetch("/api/projects").catch((e: unknown) => e);
  expect(error).toBeInstanceOf(UserMessageError);
  expect((error as UserMessageError).key).toBe("serverUnreachable");
  expect((error as Error).message).toBe("Impossible de joindre TwinStore. Vérifiez qu'il est toujours lancé, puis réessayez.");
});

it("leaves a cancelled request and a server reply alone", async () => {
  const abort = new AbortController();
  abort.abort();
  vi.stubGlobal("fetch", vi.fn(async () => { throw new DOMException("The operation was aborted.", "AbortError"); }));
  await expect(apiFetch("/api/projects", { signal: abort.signal })).rejects.toMatchObject({ name: "AbortError" });
  const reply = new Response("{}", { status: 500 });
  vi.stubGlobal("fetch", vi.fn(async () => reply));
  expect(await apiFetch("/api/projects")).toBe(reply);
});

it("preserves a custom cancellation reason carried by a Request", async () => {
  const abort = new AbortController();
  const reason = new Error("The user changed stores");
  const request = new Request("http://localhost/api/projects", { signal: abort.signal });
  abort.abort(reason);
  vi.stubGlobal("fetch", vi.fn(async () => { throw reason; }));
  await expect(apiFetch(request)).rejects.toBe(reason);
});

it.each([null, new AbortController().signal])("honors an overriding init signal instead of a cancelled Request", async signal => {
  const abort = new AbortController();
  abort.abort(new Error("Old request was cancelled"));
  const request = new Request("http://localhost/api/projects", { signal: abort.signal });
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
  await expect(apiFetch(request, { signal })).rejects.toBeInstanceOf(UserMessageError);
});
