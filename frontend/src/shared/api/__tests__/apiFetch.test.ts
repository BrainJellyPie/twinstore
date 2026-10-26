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
