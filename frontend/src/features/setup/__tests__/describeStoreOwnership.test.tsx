// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { DescribeStoreField } from "../components/DescribeStoreField";

vi.mock("@/shared/api/client", async original => ({ ...await original<typeof import("@/shared/api/client")>(), draftStoreSetup: vi.fn() }));
const draft: api.StoreSetupDraft = { name: "Old store", description: "Old description", address: "", store_type: "convenience", template_id: "urban_cvs", open_days: "7", open_hour: 0, close_hour: 24, currency: "USD", rationale: "", warnings: ["Old warning"] };
function deferred() {
  let resolve!: (value: api.StoreSetupDraft) => void, reject!: (error: Error) => void;
  return { promise: new Promise<api.StoreSetupDraft>((yes, no) => { resolve = yes; reject = no; }), resolve: (value: api.StoreSetupDraft) => resolve(value), reject: () => reject(new Error("Obsolete store failure")) };
}
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); vi.resetAllMocks(); useLocale.getState().setLocale("en"); });
function ask(text = "A campus store") {
  fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button"));
}
it.each(["text", "clear", "form", "locale", "disabled", "unmount"])("drops the answer after changing %s", async change => {
  const request = deferred(), apply = vi.fn(); vi.mocked(api.draftStoreSetup).mockReturnValue(request.promise);
  const view = render(<DescribeStoreField formKey="old" onFilled={apply} />); ask();
  if (change === "text" || change === "clear") fireEvent.change(screen.getByRole("textbox"), { target: { value: change === "clear" ? "" : "A revised store" } });
  if (change === "form") view.rerender(<DescribeStoreField formKey="new" onFilled={apply} />);
  if (change === "locale") act(() => useLocale.getState().setLocale("ko"));
  if (change === "disabled") view.rerender(<DescribeStoreField formKey="old" onFilled={apply} disabled />);
  if (change === "unmount") view.unmount();
  await act(async () => request.resolve(draft)); expect(apply).not.toHaveBeenCalled();
  expect(screen.queryByText("Old warning")).toBeNull();
});
it.each(["text", "clear", "form", "locale", "disabled"])("drops a pending error after changing %s", async change => {
  const request = deferred();vi.mocked(api.draftStoreSetup).mockReturnValue(request.promise);
  const view = render(<DescribeStoreField formKey="old" onFilled={vi.fn()} />);ask();
  if (change === "text" || change === "clear") fireEvent.change(screen.getByRole("textbox"), { target: { value: change === "clear" ? "" : "New description" } });
  if (change === "form") view.rerender(<DescribeStoreField formKey="new" onFilled={vi.fn()} />);
  if (change === "locale") act(() => useLocale.getState().setLocale("ko"));
  if (change === "disabled") view.rerender(<DescribeStoreField formKey="old" onFilled={vi.fn()} disabled />);
  await act(async () => request.reject());expect(screen.queryByRole("alert")).toBeNull();
});
it("allows a revised description while the old answer is pending and keeps the newest answer", async () => {
  const old = deferred(), current = deferred(), apply = vi.fn();vi.mocked(api.draftStoreSetup).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  render(<DescribeStoreField formKey="old" onFilled={apply} />);ask();ask("My revised shop");
  expect(api.draftStoreSetup).toHaveBeenCalledTimes(2);
  await act(async () => current.resolve({ ...draft, name: "Current store" }));
  await act(async () => old.resolve(draft));expect(apply).toHaveBeenCalledTimes(1);expect(apply.mock.calls[0]![0].name).toBe("Current store");
});
it("clears an already displayed error when the description changes", async () => {
  vi.mocked(api.draftStoreSetup).mockRejectedValue(new Error("Try again"));
  render(<DescribeStoreField formKey="old" onFilled={vi.fn()} />);ask();expect(await screen.findByRole("alert")).toBeTruthy();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "New shop description" } });expect(screen.queryByRole("alert")).toBeNull();
});
it.each(["composition", "key229", "shift"])("does not submit Enter with %s", kind => {
  render(<DescribeStoreField formKey="old" onFilled={vi.fn()} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "작은 캠퍼스 상점" } });
  fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", isComposing: kind === "composition", keyCode: kind === "key229" ? 229 : 13, shiftKey: kind === "shift" });
  expect(api.draftStoreSetup).not.toHaveBeenCalled();
});
it("bounds Unicode by code points and keeps a failed description for retry", async () => {
  vi.mocked(api.draftStoreSetup).mockRejectedValueOnce(new Error("Try again")).mockResolvedValue(draft);
  render(<DescribeStoreField formKey="old" onFilled={vi.fn()} />);ask("a".repeat(799)+"🛒x");
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("a".repeat(799)+"🛒");
  await screen.findByRole("alert");fireEvent.click(screen.getByRole("button"));await screen.findByText(/Old warning/);
  expect(vi.mocked(api.draftStoreSetup).mock.calls[0]).toEqual(vi.mocked(api.draftStoreSetup).mock.calls[1]);
});
