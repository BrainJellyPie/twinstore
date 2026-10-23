// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { uploadSkuImages } from "@/shared/api/images";
import { extractSkuImages } from "@/features/layouts/excel/extractSkuImages";
import { parseLayoutWorkbook } from "@/features/layouts/excel/parseLayoutWorkbook";
import { useLocale } from "@/shared/i18n/i18n";
import { UserMessageError } from "@/shared/i18n/userMessage";
import { LOCALES } from "@/shared/i18n/messages";
import { translate } from "@/shared/i18n/translate";
import type { Store } from "@/shared/types/domain";
import { LayoutExcelControls } from "../LayoutExcelControls";

vi.mock("@/shared/api/client", () => ({ replaceSlots: vi.fn(), getBlockedFaces: vi.fn() }));
vi.mock("@/shared/api/images", () => ({ uploadSkuImages: vi.fn() }));
vi.mock("@/features/layouts/excel/extractSkuImages", () => ({ extractSkuImages: vi.fn() }));
vi.mock("@/features/layouts/excel/parseLayoutWorkbook", () => ({ parseLayoutWorkbook: vi.fn() }));
vi.mock("@/features/layouts/excel/buildLayoutWorkbook", () => ({ buildLayoutWorkbook: vi.fn() }));

const store: Store = { id: "store", name: "Store", type: "cafe", grid_size: [8, 8], weekly_schedule: [], racks: [] };
let qc: QueryClient;
beforeEach(() => {
  useLocale.getState().setLocale("en");
  qc = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } });
  vi.mocked(api.replaceSlots).mockResolvedValue({ count: 1, cleared: [] });
  vi.mocked(extractSkuImages).mockResolvedValue({});
  vi.mocked(uploadSkuImages).mockResolvedValue([]);
  vi.mocked(parseLayoutWorkbook).mockImplementation((buffer) => ({ skuByRow: new Map([[2, String(new Uint8Array(buffer)[0])]]), slots: [{ rack_id: "shelf", block: 0, face: "N", level: 1,
    sku: String(new Uint8Array(buffer)[0]), name: "Tea", price: 100, promo: "" }] }));
});
afterEach(() => { cleanup(); qc.clear(); vi.resetAllMocks(); });

function view(projectId = "p", setupId = "s") {
  return <QueryClientProvider client={qc}><LayoutExcelControls store={store} projectId={projectId} setupId={setupId} /></QueryClientProvider>;
}

function file(id: number, read?: () => Promise<ArrayBuffer>) {
  const value = new File([String(id)], `${id}.xlsx`);
  Object.defineProperty(value, "arrayBuffer", { value: read ?? (() => Promise.resolve(new Uint8Array([id]).buffer)) });
  return value;
}

function choose(container: HTMLElement, value: File) {
  fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [value] } });
}

it.each(LOCALES.flatMap(({ code }) => (["excelSheetTooWide", "excelDuplicateColumn"] as const)
  .map((key) => ({ code, key }))))("blocks invalid sheet uploads and updates $key in $code", async ({ code, key }) => {
  const details: Record<string, string> = key === "excelDuplicateColumn" ? { column: "sku" } : {};
  vi.mocked(parseLayoutWorkbook).mockImplementationOnce(() => { throw new UserMessageError(key, details); });
  const rendered = render(view());
  choose(rendered.container, file(1));
  await screen.findByText(translate("en", key, details));
  act(() => useLocale.getState().setLocale(code));
  expect(screen.getByText(translate(code, key, details))).toBeTruthy();
  expect(extractSkuImages).not.toHaveBeenCalled();
  expect(uploadSkuImages).not.toHaveBeenCalled();
  expect(api.replaceSlots).not.toHaveBeenCalled();
  choose(rendered.container, file(2));
  await waitFor(() => expect(api.replaceSlots).toHaveBeenCalledOnce());
});

type Stage = "read" | "extract" | "images";
function pause(stage: Stage) {
  let resolve!: () => void;
  const gate = new Promise<void>((done) => { resolve = done; });
  let upload = file(1);
  if (stage === "read") upload = file(1, async () => { await gate; return new Uint8Array([1]).buffer; });
  if (stage === "extract") vi.mocked(extractSkuImages).mockImplementationOnce(async () => { await gate; return {}; });
  if (stage === "images") {
    vi.mocked(extractSkuImages).mockResolvedValueOnce({ tea: { bytes: new Uint8Array([1]), extension: "png" } });
    vi.mocked(uploadSkuImages).mockImplementationOnce(async () => { await gate; return []; });
  }
  return { upload, resolve, reached: async () => {
    if (stage === "extract") await waitFor(() => expect(extractSkuImages).toHaveBeenCalled());
    if (stage === "images") await waitFor(() => expect(uploadSkuImages).toHaveBeenCalled());
  } };
}

it.each<Stage>(["read", "extract", "images"])("reserves the upload through %s so another file cannot overtake it", async (stage) => {
  const pending = pause(stage);
  const rendered = render(view());
  choose(rendered.container, pending.upload);
  await pending.reached();
  const disabled = (screen.getByRole("button", { name: "Upload" }) as HTMLButtonElement).disabled;
  choose(rendered.container, file(2));
  await act(async () => { pending.resolve(); });
  await waitFor(() => expect(api.replaceSlots).toHaveBeenCalled());
  expect(vi.mocked(api.replaceSlots).mock.calls.map((call) => call[2][0]?.sku)).toEqual(["1"]);
  expect(disabled).toBe(true);
  await waitFor(() => expect((screen.getByRole("button", { name: "Upload" }) as HTMLButtonElement).disabled).toBe(false));
});

it.each<Stage>(["read", "extract", "images"])("does not save after unmount during %s", async (stage) => {
  const pending = pause(stage);
  const rendered = render(view());
  choose(rendered.container, pending.upload);
  await pending.reached();
  rendered.unmount();
  await act(async () => { pending.resolve(); });
  expect(api.replaceSlots).not.toHaveBeenCalled();
});

it.each(["project", "setup"])("abandons staged input on %s change and accepts the new layout's file", async (scope) => {
  const pending = pause("read");
  const rendered = render(view());
  choose(rendered.container, pending.upload);
  const project = scope === "project" ? "next" : "p";
  const setup = scope === "setup" ? "next" : "s";
  rendered.rerender(view(project, setup));
  choose(rendered.container, file(2));
  await waitFor(() => expect(api.replaceSlots).toHaveBeenCalled());
  await act(async () => { pending.resolve(); });
  expect(api.replaceSlots).toHaveBeenCalledTimes(1);
  expect(vi.mocked(api.replaceSlots).mock.calls[0]?.slice(0, 2)).toEqual([project, setup]);
  expect(vi.mocked(api.replaceSlots).mock.calls[0]?.[2][0]?.sku).toBe("2");
});

it.each(["read", "parse", "extract", "save"])("releases the upload after a %s failure so a corrected file can be tried", async (stage) => {
  const rendered = render(view());
  let upload = file(1);
  if (stage === "read") upload = file(1, () => Promise.reject(new Error("Unreadable")));
  if (stage === "parse") vi.mocked(parseLayoutWorkbook).mockImplementationOnce(() => { throw new Error("Invalid workbook"); });
  if (stage === "extract") vi.mocked(extractSkuImages).mockRejectedValueOnce(new Error("Invalid image data"));
  if (stage === "save") vi.mocked(api.replaceSlots).mockRejectedValueOnce(new Error("Layout locked"));
  choose(rendered.container, upload);
  await waitFor(() => expect((screen.getByRole("button", { name: "Upload" }) as HTMLButtonElement).disabled).toBe(false));
  choose(rendered.container, file(2));
  await waitFor(() => expect(vi.mocked(api.replaceSlots).mock.lastCall?.[2][0]?.sku).toBe("2"));
  expect(api.replaceSlots).toHaveBeenCalledTimes(stage === "save" ? 2 : 1);
});

it("keeps the existing best-effort image behavior and saves product rows after image upload fails", async () => {
  vi.mocked(extractSkuImages).mockResolvedValueOnce({ tea: { bytes: new Uint8Array([1]), extension: "png" } });
  vi.mocked(uploadSkuImages).mockRejectedValueOnce(new Error("Image unavailable"));
  const rendered = render(view());
  choose(rendered.container, file(1));
  await waitFor(() => expect(api.replaceSlots).toHaveBeenCalledTimes(1));
  await waitFor(() => expect((screen.getByRole("button", { name: "Upload" }) as HTMLButtonElement).disabled).toBe(false));
});

it.each(["new image", "no image", "failed image"])("preserves saved photo references except for a successfully uploaded %s", async (mode) => {
  const original = "/api/projects/p/product-photo-files/" + "a".repeat(64);
  const replacement = "/api/projects/p/images?sku=1&v=new";
  vi.mocked(parseLayoutWorkbook).mockReturnValueOnce({ skuByRow: new Map([[2, "1"], [3, "1"], [4, "2"]]), slots: ["1", "1", "2"].map((sku) => ({
    rack_id: "shelf", block: 0, face: "N" as const, level: 1, sku, name: "Tea", price: 100, promo: "", image_url: original,
  })) });
  if (mode !== "no image") vi.mocked(extractSkuImages).mockResolvedValueOnce({ "1": { bytes: new Uint8Array([1]), extension: "png" } });
  if (mode === "new image") vi.mocked(uploadSkuImages).mockResolvedValueOnce([{ sku: "1", url: replacement }]);
  if (mode === "failed image") vi.mocked(uploadSkuImages).mockRejectedValueOnce(new Error("Image failed"));
  const rendered = render(view());
  choose(rendered.container, file(1));
  await waitFor(() => expect(api.replaceSlots).toHaveBeenCalledTimes(1));
  const expected = mode === "new image" ? replacement : original;
  expect(vi.mocked(api.replaceSlots).mock.calls[0]?.[2].map((row) => row.image_url)).toEqual([expected, expected, original]);
});
