// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { EmptyFloorSlot } from "../EmptyFloorSlot";
import { useSimulationStore } from "@/stores/simulationStore";

afterEach(() => { cleanup(); useSimulationStore.getState().setActiveTab("dashboard"); });

it("leads from an empty floor to the side panel's first step", () => {
  useSimulationStore.getState().setActiveTab("settings");
  render(<EmptyFloorSlot />);
  expect(screen.getByText("Your floor is empty.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Go to Step 1: Floor configuration" }));
  expect(useSimulationStore.getState().activeTab).toBe("dashboard");
});
