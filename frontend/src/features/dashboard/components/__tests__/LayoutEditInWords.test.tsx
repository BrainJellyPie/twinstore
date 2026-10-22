// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { applyLayoutEdit, draftLayoutEdit, type LayoutEditDraft } from "@/shared/api/marketing";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { LayoutEditInWords } from "../LayoutEditInWords";

vi.mock("@/shared/api/marketing", async (original) => ({
  ...await original<typeof import("@/shared/api/marketing")>(), draftLayoutEdit: vi.fn(), applyLayoutEdit: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); useSimulationStore.getState().setSelectedSetupId(null); useAssistStore.setState({ pending: null }); });

const DRAFT: LayoutEditDraft = {
  source_sha256: "a".repeat(64),
  name: "Promo week", summary: "A sign and a lower price.",
  changes: [{ kind: "promo", sku: "chips", promo: "SALE" }, { kind: "price", sku: "cola", price: 99, keep_reference: true }],
  applied: ["Chips: SALE sign", "Cola: $1.29 → $0.99"], warnings: ['no unique product "Imaginary soda" in this layout'],
};

function mount() {
  render(<QueryClientProvider client={new QueryClient()}><LayoutEditInWords projectId="p" setupId="s1" /></QueryClientProvider>);
}

it("drafts edits from words, shows them in words and saves them as a new layout that opens next", async () => {
  vi.mocked(draftLayoutEdit).mockResolvedValue(DRAFT);
  vi.mocked(applyLayoutEdit).mockResolvedValue({ id: "s2", name: "Promo week sale", applied: DRAFT.applied, warnings: [] });
  mount();
  fireEvent.change(screen.getByLabelText("Layout changes in words"), { target: { value: "SALE sign on the chips, cola at 99 cents" } });
  fireEvent.click(screen.getByRole("button", { name: "Draft the edits" }));
  const list = await screen.findByRole("list", { name: "Drafted edits" });
  expect(list.textContent).toContain("Cola: $1.29 → $0.99");
  expect(draftLayoutEdit).toHaveBeenCalledWith("p", "s1", "SALE sign on the chips, cola at 99 cents");
  expect(screen.getByText(/Imaginary soda/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Name of the new layout"), { target: { value: "Promo week sale" } });
  fireEvent.click(screen.getByRole("button", { name: "Save as a new layout" }));
  await waitFor(() => expect(useSimulationStore.getState().selectedSetupId).toBe("s2"));
  expect(applyLayoutEdit).toHaveBeenCalledWith("p", "s1", { name: "Promo week sale", changes: DRAFT.changes, source_sha256: DRAFT.source_sha256, request_id: expect.stringMatching(/^[0-9a-f]{32}$/) });
  expect((screen.getByLabelText("Layout changes in words") as HTMLTextAreaElement).value).toBe("");
});

it("drops a draft once the words change, so an older draft is never saved for new words", async () => {
  vi.mocked(draftLayoutEdit).mockResolvedValue(DRAFT);
  mount();
  const box = screen.getByLabelText("Layout changes in words");
  fireEvent.change(box, { target: { value: "SALE sign on the chips" } });
  fireEvent.keyDown(box, { key: "Enter" });
  await screen.findByRole("button", { name: "Save as a new layout" });
  fireEvent.change(box, { target: { value: "SALE sign on the chips and the nuts" } });
  expect(screen.queryByRole("button", { name: "Save as a new layout" })).toBeNull();
});

it("drafts instructions routed from the command palette once", async () => {
  vi.mocked(draftLayoutEdit).mockResolvedValue(DRAFT);
  useAssistStore.getState().send({ projectId: "p", destination: "layout_edit", text: "SALE sign on the chips" });
  mount();
  expect(await screen.findByRole("list", { name: "Drafted edits" })).toBeTruthy();
  expect(draftLayoutEdit).toHaveBeenCalledTimes(1);
  expect((screen.getByLabelText("Layout changes in words") as HTMLTextAreaElement).value).toBe("SALE sign on the chips");
});
