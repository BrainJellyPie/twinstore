// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { focusPlayWhenShown } from "../focusPlay";

beforeEach(() => vi.useFakeTimers());
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); document.body.replaceChildren(); });

it.each([true, false])("waits until playback can actually take focus (initially present=%s)", (present) => {
  const play = document.createElement("button");
  play.setAttribute("data-playback-play", "");
  play.disabled = true;
  if (present) document.body.append(play);
  focusPlayWhenShown();
  expect(document.activeElement).not.toBe(play);
  play.disabled = false;
  if (!present) document.body.append(play);
  vi.advanceTimersByTime(100);
  expect(document.activeElement).toBe(play);
});

it("gives up when playback stays unavailable and does not focus it later", () => {
  const play = document.createElement("button");
  play.setAttribute("data-playback-play", "");
  play.disabled = true;
  document.body.append(play);
  focusPlayWhenShown();
  vi.advanceTimersByTime(6000);
  expect(vi.getTimerCount()).toBe(0);
  play.disabled = false;
  vi.advanceTimersByTime(1000);
  expect(document.activeElement).not.toBe(play);
});
