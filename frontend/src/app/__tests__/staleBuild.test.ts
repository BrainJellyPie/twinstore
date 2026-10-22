// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { isStaleBuildError, reloadForNewVersion } from "../staleBuild";

afterEach(() => { sessionStorage.clear(); vi.restoreAllMocks(); });

it("recognizes the browsers' messages for a script chunk that is gone", () => {
  for (const message of [
    "Failed to fetch dynamically imported module: http://127.0.0.1:8000/assets/settings-3f9a1c.js",   // Chrome
    "error loading dynamically imported module: http://127.0.0.1:8000/assets/x.js",                    // Firefox
    "Importing a module script failed.",                                                               // Safari
    "Unable to preload CSS for /assets/index-9a8b.css",
  ]) expect(isStaleBuildError(new Error(message))).toBe(true);
  expect(isStaleBuildError(new Error("Cannot read properties of undefined"))).toBe(false);
  expect(isStaleBuildError(null)).toBe(false);
});

it("reloads once, and shows the error if the reload did not help", () => {
  const reload = vi.fn();
  expect(reloadForNewVersion(reload, 1_000_000)).toBe(true);
  expect(reloadForNewVersion(reload, 1_030_000)).toBe(false);   // 30 s later: the new page failed too
  expect(reloadForNewVersion(reload, 1_100_000)).toBe(true);    // a later update
  expect(reload).toHaveBeenCalledTimes(2);
});

it("never reloads without session storage, so it cannot loop", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
  const reload = vi.fn();
  expect(reloadForNewVersion(reload)).toBe(false);
  expect(reload).not.toHaveBeenCalled();
});
