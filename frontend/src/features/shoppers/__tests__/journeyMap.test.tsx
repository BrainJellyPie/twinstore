// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";

import type { Journey, JourneyStep } from "@/shared/api/interview";
import type { Store } from "@/shared/types/domain";
import { useLocale } from "@/shared/i18n/i18n";
import { JourneyMap } from "../JourneyView";

afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });

const step = (index: number, action: string, product_name = "") => ({ index, time: "10:05", elapsed_sec: 0, action, rack_id: "r1",
  rack: "Drinks", face: "N", product_sku: "", product_name, price: 0, quantity: 0, origin: "", thought: "", sees_products: true,
  x: 2, y: 3 }) as unknown as JourneyStep;
const journey = { run_id: "run1", currency: "USD", path: [[0, 2, 3]], shelves: {},
  steps: [step(2, "browse"), step(3, "buy", "Cola 500ml")] } as unknown as Journey;
const store = { grid_size: [6, 6], racks: [
  { id: "door", type: "entrance", rack_name: "", position: [0, 0], shape: [[1]], rotation: 0, slots: [] },
  { id: "r1", type: "shelf", rack_name: "Drinks", position: [2, 3], shape: [[1]], rotation: 0, slots: [] },
] } as unknown as Store;

it.each([["en", "2. Looks at\n3. Takes Cola 500ml"], ["ko", "2. 살펴봄\n3. 집음 Cola 500ml"]])(
  "lists the steps at a spot in the selected language (%s)", (locale, expected) => {
    useLocale.getState().setLocale(locale as "en" | "ko");
    const { container } = render(<JourneyMap journey={journey} store={store} active={new Set()} onHover={() => {}} />);
    expect(container.querySelector("g > title")!.textContent).toBe(expected);
  });

it("names an unnamed rack by its type in the selected language", () => {
  useLocale.getState().setLocale("ko");
  const { container } = render(<JourneyMap journey={journey} store={store} active={new Set()} onHover={() => {}} />);
  expect([...container.querySelectorAll("rect > title")].map((title) => title.textContent)).toEqual(["입구", "Drinks"]);
});
