// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";

import { quitLauncher } from "../launcher";

afterEach(() => { document.body.replaceChildren(); vi.unstubAllGlobals(); });

it("asks the launcher to stop, then covers the app with the stopped note in the given words", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}"));
  vi.stubGlobal("fetch", fetch);
  await quitLauncher({ title: "TwinStore가 종료되었습니다", body: "<b>이제</b> 탭을 닫아도 됩니다." });
  expect(fetch).toHaveBeenCalledWith("/__twinstore/quit", { method: "POST", headers: { "X-TwinStore": "1" } });
  const note = document.querySelector("[data-twinstore-stopped]")!;
  expect(note.getAttribute("role")).toBe("status");
  expect(note.textContent).toContain("TwinStore가 종료되었습니다");
  expect(note.querySelector("b")).toBeNull();               // text, never markup
});

it("shows the note even when the launcher is already gone", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  await quitLauncher();
  expect(document.body.textContent).toContain("TwinStore stopped");
});
