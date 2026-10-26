// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";

import { smoothScroll } from "../motion";

afterEach(() => vi.unstubAllGlobals());

const prefers = (reduce: boolean) => vi.stubGlobal("matchMedia", (query: string) => ({ matches: reduce && query.includes("reduce") }));

it("jumps instead of gliding when the system asks for less motion", () => {
  prefers(true);
  expect(smoothScroll()).toBe("auto");
  prefers(false);
  expect(smoothScroll()).toBe("smooth");
});
