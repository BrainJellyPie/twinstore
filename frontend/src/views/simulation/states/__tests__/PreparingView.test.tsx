// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { PreparingView } from "../PreparingView";
import { translate, useLocale } from "@/shared/i18n/i18n";
import { LOCALES } from "@/shared/i18n/messages";
import type { SetupGenerationState } from "@/shared/queries/useSetupGeneration";

afterEach(() => { cleanup(); useLocale.getState().setLocale("en"); });
const failedLayout: SetupGenerationState = { phase: "failed", kind: "layout", currentGenId: "layout_generation", error: "Invalid image", retry: vi.fn(), retrying: false };
function show(generation: SetupGenerationState = failedLayout) {
  const props = { generation, contextKind: "layout" as "layout" | "persona", onAbandonProject: vi.fn<() => void | Promise<void>>(),
    onBackToStores: vi.fn(), projectName: "우리商店 Café", layouts: [{ id: "failed_layout", name: "Failed floor" }, { id: "ready_layout", name: "Good floor" }], selectedSetupId: "failed_layout", onLayoutSelect: vi.fn() };
  return { ...render(<PreparingView {...props} />), props };
}

it("does not delete a store when the user only opens the start-over decision", () => {
  const { props } = show();
  fireEvent.click(screen.getByRole("button", { name: "Delete store and start over" }));
  expect(props.onAbandonProject).not.toHaveBeenCalled();
  expect(screen.getByRole("alertdialog")).toBeTruthy();
});

it.each(LOCALES)("reviews the exact store, cancels safely and returns focus in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); const { props } = show();
  const button = screen.getByRole("button", { name: translate(code, "deleteStoreAndStartOver") }); fireEvent.click(button);
  const dialog = screen.getByRole("alertdialog", { name: translate(code, "deleteStoreTitle") });
  expect(dialog.textContent).toContain(props.projectName); expect(props.onAbandonProject).not.toHaveBeenCalled();
  fireEvent.click(within(dialog).getByRole("button", { name: translate(code, "cancel") }));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(props.onAbandonProject).not.toHaveBeenCalled(); expect(document.activeElement).toBe(button);
});

it.each(LOCALES)("leaves or selects another layout without deleting in $code", ({ code }) => {
  useLocale.getState().setLocale(code); const { props } = show();
  fireEvent.change(screen.getByRole("combobox", { name: translate(code, "switchPreparingLayout") }), { target: { value: "ready_layout" } });
  expect(props.onLayoutSelect).toHaveBeenCalledWith("ready_layout");
  fireEvent.change(screen.getByRole("combobox", { name: translate(code, "switchPreparingLayout") }), { target: { value: "failed_layout" } });
  expect(props.onLayoutSelect).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "backToStores") }));
  expect(props.onBackToStores).toHaveBeenCalledOnce(); expect(props.onAbandonProject).not.toHaveBeenCalled();
});

it("sends only one confirmed deletion and leaves a safe exit available while it is pending", async () => {
  let resolve!: () => void; const pending = new Promise<void>(done => { resolve = done; });
  const { props } = show(); props.onAbandonProject.mockReturnValue(pending);
  fireEvent.click(screen.getByRole("button", { name: "Delete store and start over" }));
  const confirm = within(screen.getByRole("alertdialog")).getByRole("button", { name: "Delete store and start over" });
  fireEvent.click(confirm); fireEvent.click(confirm);
  expect(props.onAbandonProject).toHaveBeenCalledOnce();
  expect(screen.getByRole("heading", { name: "Deleting store…" })).toBeTruthy();
  expect((screen.getByRole("combobox", { name: "Switch layout" }) as HTMLSelectElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Back to stores" })); expect(props.onBackToStores).toHaveBeenCalledOnce();
  await act(async () => resolve());
});

it.each(LOCALES)("shows deletion failures and supports an explicit retry in $code", async ({ code }) => {
  useLocale.getState().setLocale(code); const { props } = show();
  props.onAbandonProject.mockRejectedValueOnce(new Error("Deletion unavailable"));
  const open = () => fireEvent.click(screen.getByRole("button", { name: translate(code, "deleteStoreAndStartOver") }));
  open(); fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: translate(code, "deleteStoreAndStartOver") }));
  const message = await screen.findByText("Deletion unavailable");
  const notice = message.closest('[role="alert"]');
  expect(notice?.textContent).toContain(translate(code, "deleteStoreFailed"));
  await waitFor(() => expect(document.activeElement).toBe(notice));
  expect(props.onBackToStores).not.toHaveBeenCalled();
  open(); expect(props.onAbandonProject).toHaveBeenCalledOnce();
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: translate(code, "deleteStoreAndStartOver") }));
  await waitFor(() => expect(props.onAbandonProject).toHaveBeenCalledTimes(2));
});

it("closes a stale deletion decision when generation recovers and does not reopen it on a later failure", async () => {
  const { props, rerender } = show(); fireEvent.click(screen.getByRole("button", { name: "Delete store and start over" }));
  rerender(<PreparingView {...props} generation={{ ...failedLayout, phase: "persona", kind: "persona", error: null }} />);
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  rerender(<PreparingView {...props} generation={failedLayout} />);
  expect(screen.queryByRole("alertdialog")).toBeNull(); expect(props.onAbandonProject).not.toHaveBeenCalled();
});

it("cancels a deletion decision with Escape and keeps the store", async () => {
  const { props } = show(); const button = screen.getByRole("button", { name: "Delete store and start over" }); fireEvent.click(button);
  fireEvent.keyDown(screen.getByRole("alertdialog"), { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  expect(props.onAbandonProject).not.toHaveBeenCalled(); expect(document.activeElement).toBe(button);
});

it("uses a localized untitled fallback without changing the store name", () => {
  const { props, rerender } = show(); rerender(<PreparingView {...props} projectName="  " layouts={[props.layouts[0]!, { id: "ready_layout", name: "" }]} />);
  expect(screen.getByRole("option", { name: "Layout 2" }).getAttribute("value")).toBe("ready_layout");
  fireEvent.click(screen.getByRole("button", { name: "Delete store and start over" }));
  expect(screen.getByRole("alertdialog").textContent).toContain("Untitled store"); expect(props.onAbandonProject).not.toHaveBeenCalled();
});

it.each([
  ["layout", "layout", "Analyzing layout…"], ["idle", "layout", "Preparing layout analysis…"],
  ["completed", "persona", "Preparing customer generation…"],
] as const)("announces %s progress in %s context without starting another generation", (phase, contextKind, label) => {
  const retry = vi.fn(); const { props, rerender } = show({ ...failedLayout, phase, kind: contextKind, error: null, retry });
  rerender(<PreparingView {...props} contextKind={contextKind} />);
  expect(screen.getByRole("heading", { name: label })).toBeTruthy(); expect(screen.getByRole("status")).toBeTruthy(); expect(retry).not.toHaveBeenCalled();
});

it("ignores a late deletion failure after the user leaves", async () => {
  let reject!: (error: Error) => void; const pending = new Promise<void>((_resolve, fail) => { reject = fail; });
  const { props, unmount } = show(); props.onAbandonProject.mockReturnValue(pending);
  fireEvent.click(screen.getByRole("button", { name: "Delete store and start over" }));
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Delete store and start over" })); unmount();
  await act(async () => reject(new Error("Late deletion error")));
  expect(props.onBackToStores).not.toHaveBeenCalled();
});

it("offers customer retry when the known generation kind disagrees with stale layout context", () => {
  const retry = vi.fn(); show({ ...failedLayout, kind: "persona", retry });
  expect(screen.getByRole("heading", { name: "Customer generation failed" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Delete store and start over" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Try again" })); expect(retry).toHaveBeenCalledOnce();
});

it("uses layout recovery for a known layout failure even when the context has moved to customers", () => {
  const { props, rerender } = show(); rerender(<PreparingView {...props} contextKind="persona" />);
  expect(screen.getByRole("heading", { name: "Layout analysis failed" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
});

it.each(LOCALES)("shows native progress, idle and retry states without starting work automatically in $code", ({ code }) => {
  useLocale.getState().setLocale(code); const retry = vi.fn();
  const generation = { ...failedLayout, phase: "persona" as const, kind: "persona" as const, error: null, retry };
  const { props, rerender } = show(generation);
  expect(screen.getByRole("heading", { name: translate(code, "generatingPersonas") })).toBeTruthy(); expect(retry).not.toHaveBeenCalled();
  rerender(<PreparingView {...props} contextKind="persona" generation={{ ...generation, phase: "idle" }} />);
  expect(screen.getByRole("heading", { name: translate(code, "personasNotGenerated") })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "generate") })); expect(retry).toHaveBeenCalledOnce();
  rerender(<PreparingView {...props} contextKind="persona" generation={{ ...generation, phase: "failed", retrying: true }} />);
  expect((screen.getByRole("button", { name: translate(code, "tryingAgain") }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: translate(code, "tryingAgain") })); expect(retry).toHaveBeenCalledOnce();
});

it.each(LOCALES)("offers a progress reload without generation or deletion for status errors in $code", ({ code }) => {
  useLocale.getState().setLocale(code); const retry = vi.fn(); show({ ...failedLayout, errorSource: "status", retry });
  expect(screen.getByRole("heading", { name: translate(code, "generationStatusUnavailable") })).toBeTruthy();
  expect(screen.queryByRole("button", { name: translate(code, "deleteStoreAndStartOver") })).toBeNull();
  expect(screen.queryByRole("button", { name: translate(code, "tryAgain") })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "reloadGenerationStatus") })); expect(retry).toHaveBeenCalledOnce();
});

it.each(LOCALES)("checks history before offering generation and leaves a safe exit available in $code", ({ code }) => {
  useLocale.getState().setLocale(code);
  const { props, rerender } = show({ ...failedLayout, phase: "idle", kind: null, error: null, loadingStatus: true });
  rerender(<PreparingView {...props} contextKind="persona" />);
  expect(screen.getByRole("heading", { name: translate(code, "checkingGenerationStatus") })).toBeTruthy();
  expect(screen.queryByRole("button", { name: translate(code, "generate") })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: translate(code, "backToStores") })); expect(props.onBackToStores).toHaveBeenCalledOnce();
});

it("disables progress reload while it is pending and closes a stale delete decision", async () => {
  const { props, rerender } = show(); fireEvent.click(screen.getByRole("button", { name: "Delete store and start over" }));
  rerender(<PreparingView {...props} generation={{ ...failedLayout, errorSource: "status", loadingStatus: true, retrying: true }} />);
  await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
  const button = screen.getByRole("button", { name: "Checking progress…" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); fireEvent.click(button); expect(props.generation.retry).not.toHaveBeenCalled();
});

it("keeps keyboard focus in recovery when a progress reload discovers a real generation failure", () => {
  const { props, rerender } = show({ ...failedLayout, errorSource: "status" });
  const reload = screen.getByRole("button", { name: "Reload progress" }); reload.focus(); fireEvent.click(reload);
  rerender(<PreparingView {...props} generation={{ ...failedLayout, kind: "persona", errorSource: "generation" }} />);
  expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Customer generation failed" }));
});

it("does not steal focus if the user moves elsewhere during a progress reload", () => {
  const { props, rerender } = show({ ...failedLayout, errorSource: "status" });
  const reload = screen.getByRole("button", { name: "Reload progress" }); reload.focus(); fireEvent.click(reload);
  const back = screen.getByRole("button", { name: "Back to stores" }); back.focus();
  rerender(<PreparingView {...props} generation={{ ...failedLayout, kind: "persona", errorSource: "generation" }} />);
  expect(document.activeElement).toBe(back);
});

it("says customer generation is waiting for the local model and why", () => {
  const note = "Google Gemini turned the API key down (API key not valid); waiting for the local model: Downloading Qwen3.5-2B (40%)";
  show({ phase: "persona", kind: "persona", currentGenId: "persona_generation", error: null, note, retry: vi.fn(), retrying: false, loadingStatus: false });
  expect(screen.getByText(translate("en", "generationWaitsForLocalModel"))).toBeTruthy();
  expect(screen.getByText(note)).toBeTruthy();
  cleanup();
  show({ phase: "persona", kind: "persona", currentGenId: "persona_generation", error: null, note: null, retry: vi.fn(), retrying: false, loadingStatus: false });
  expect(screen.queryByText(translate("en", "generationWaitsForLocalModel"))).toBeNull();
});
