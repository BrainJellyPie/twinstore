// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { Store } from "@/shared/types/domain";
import { SettingsPanel } from "../SettingsPanel";

afterEach(cleanup);

const store: Store = { id: "store", name: "Corner", type: "convenience", grid_size: [8, 8], racks: [], weekly_schedule: [
  ...[1, 2, 3, 4, 5].map((day) => ({ day, is_open: true, open_hour: 7, close_hour: 24 })),
  { day: 6, is_open: true, open_hour: 10, close_hour: 20 },
  { day: 7, is_open: false, open_hour: 0, close_hour: 0 },
] };

it("shows every day's opening hours, closing at midnight as 24:00 and keeping closed days apart", () => {
  render(<SettingsPanel store={store} summary={null} personas={[]} location="" />);
  const hours = screen.getByText("Opening hours").nextElementSibling!;
  expect(hours.textContent).toBe("Mon–Fri: 07:00–24:00; Sat: 10:00–20:00; Sun: Closed");
});

it("does not merge days across a closed day", () => {
  const split: Store = { ...store, weekly_schedule: [1, 2, 4, 5].map((day) => ({ day, is_open: true, open_hour: 9, close_hour: 18 })) };
  render(<SettingsPanel store={split} summary={null} personas={[]} location="" />);
  expect(screen.getByText("Opening hours").nextElementSibling!.textContent).toBe("Mon–Tue, Thu–Fri: 09:00–18:00; Wed, Sat–Sun: Closed");
});
