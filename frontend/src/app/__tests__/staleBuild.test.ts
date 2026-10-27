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

const up = () => Promise.resolve();

it("reloads once, and shows the error if the reload did not help", async () => {
  const reload = vi.fn();
  expect(await reloadForNewVersion(reload, 1_000_000, up)).toBe("reloading");
  expect(await reloadForNewVersion(reload, 1_030_000, up)).toBe("show");   // 30 s later: the new page failed too
  expect(await reloadForNewVersion(reload, 1_100_000, up)).toBe("reloading");    // a later update
  expect(reload).toHaveBeenCalledTimes(2);
});

it("does not reload while the server is not answering, and reloads once it answers", async () => {
  const reload = vi.fn();
  expect(await reloadForNewVersion(reload, 1_000_000, () => Promise.reject(new TypeError("Failed to fetch")))).toBe("offline");
  expect(reload).not.toHaveBeenCalled();
  expect(await reloadForNewVersion(reload, 1_010_000, up)).toBe("reloading");
  expect(reload).toHaveBeenCalledOnce();
});

it.each([0, 1])("overlapping server checks reload only once when request %s answers first", async (first) => {
  const reload = vi.fn();
  const finish: Array<() => void> = [];
  const checks = [0, 1].map(() => {
    const pending = new Promise<void>((resolve) => { finish.push(resolve); });
    return reloadForNewVersion(reload, 1_000_000, () => pending);
  });
  expect(reload).not.toHaveBeenCalled();
  finish[first]!();
  expect(await checks[first]).toBe("reloading");
  finish[1 - first]!();
  expect(await checks[1 - first]).toBe("show");
  expect(reload).toHaveBeenCalledOnce();
});

it("never reloads without session storage, so it cannot loop", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
  const reload = vi.fn();
  expect(await reloadForNewVersion(reload, Date.now(), up)).toBe("show");
  expect(reload).not.toHaveBeenCalled();
});
