// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import type { DashboardTab } from "@/stores/simulationStore";
import type { Store } from "@/shared/types/domain";
import { SidePanel } from "../SidePanel";

vi.mock("@/features/dashboard/components/DashboardPanel", () => ({ DashboardPanel: () => null }));
vi.mock("@/features/dashboard/components/SettingsPanel", () => ({ SettingsPanel: () => null }));
vi.mock("@/features/shoppers/ShopperPanel", () => ({ ShopperPanel: () => <p>Shopper list</p> }));
afterEach(cleanup);

function Harness() {
  const [tab, setTab] = useState<DashboardTab>("dashboard");
  return <SidePanel mode="playback" customers={[]} minTime={0} maxTime={1} store={{ racks: [] } as unknown as Store} summary={null}
    personas={[]} location="" projectId="p" runId="r" activeTab={tab} setActiveTab={setTab} />;
}

it("moves focus to the Shoppers tab when the Track a shopper card opens it", () => {
  render(<Harness />);
  const card = screen.getByRole("button", { name: /Track a shopper/ });
  card.focus();
  fireEvent.click(card);
  expect(screen.getByText("Shopper list")).toBeTruthy();
  expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Shoppers" }));
});
