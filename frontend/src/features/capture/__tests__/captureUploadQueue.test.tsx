// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { webcrypto } from "node:crypto";
import * as api from "@/shared/api/client";
import { setupWithKey } from "@/features/settings/__tests__/modelSetupWithKey";
import { CaptureUploadQueue } from "../CaptureUploadQueue";
vi.mock("@tanstack/react-router", async (original) => ({
  ...(await original<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}));
vi.mock("@/shared/api/client", async (original) => ({
  ...(await original<typeof import("@/shared/api/client")>()),
  getProject: vi.fn(),
  getModels: vi.fn(),
  createCapture: vi.fn(),
  getCapture: vi.fn(),
  getModelSetup: vi.fn(),
}));
const status: api.CaptureStatus = {
  capture_id: "cap_a",
  status: "completed",
  stage: "done",
  progress: 1,
  error: "",
  options: {
    detector: "classic",
    model: "none",
    currency: "USD",
    rack_type: "shelf",
    label: "",
  },
  image_name: "shelf.png",
  image_size: [200, 200],
  created_at: "",
  finished_at: "",
  items: 2,
  facings: 2,
  gaps: 0,
  levels: 1,
  applied_setup_ids: [],
};
let qc: QueryClient;
const accepted = vi.fn(),
  review = vi.fn();
beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  vi.mocked(api.getProject).mockResolvedValue({
    metadata: { currency: "USD" },
  } as Awaited<ReturnType<typeof api.getProject>>);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(api.createCapture).mockImplementation(async (_pid, file) => ({
    ...status,
    capture_id: `cap_${file.name}`,
  }));
  vi.mocked(api.getCapture).mockResolvedValue({ status, result: null });
});
afterEach(() => {
  cleanup();
  qc.clear();
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});
function mount() {
  return render(
    <QueryClientProvider client={qc}>
      <CaptureUploadQueue
        projectId="p"
        onAccepted={accepted}
        onReview={review}
      />
    </QueryClientProvider>,
  );
}
async function choose(files: File[]) {
  await waitFor(() =>
    expect(
      (
        screen.getByRole("button", {
          name: "Choose photos or drop them here",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false),
  );
  fireEvent.change(screen.getByLabelText("Shelf photo files"), {
    target: { files },
  });
  await waitFor(() =>
    expect(screen.queryByText("Checking selected files…")).toBeNull(),
  );
}
it("selects multiple files once, starts explicitly, waits for each result and links review", async () => {
  mount();
  await choose([
    new File(["first"], "one.png", { type: "image/png" }),
    new File(["second"], "two.png", { type: "image/png" }),
  ]);
  expect(screen.getByText(/0 of 2 ready/)).toBeTruthy();
  expect(api.createCapture).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/2 of 2 ready/);
  expect(api.createCapture).toHaveBeenCalledTimes(2);
  expect(api.createCapture).toHaveBeenNthCalledWith(
    1,
    "p",
    expect.any(File),
    expect.objectContaining({
      currency: "USD",
      request_id: expect.stringMatching(/^[0-9a-f]{32}$/),
    }),
    expect.any(AbortSignal),
  );
  expect(vi.mocked(api.getCapture).mock.invocationCallOrder[0]!).toBeLessThan(
    vi.mocked(api.createCapture).mock.invocationCallOrder[1]!,
  );
  fireEvent.click(screen.getAllByRole("button", { name: "Review photo" })[0]!);
  expect(review).toHaveBeenCalledWith("cap_one.png");
  expect(accepted).toHaveBeenCalledTimes(2);
});
const file = (name: string, content = name) =>
  new File([content], name, { type: "image/png" });
function deferred<T>() {
  let resolve!: (value: T) => void;
  return {
    promise: new Promise<T>((r) => {
      resolve = r;
    }),
    resolve: (value: T) => resolve(value),
  };
}
it("deduplicates bytes across filenames but keeps distinct photos sharing a name", async () => {
  mount();
  await choose([
    file("same.png", "a"),
    file("renamed.png", "a"),
    file("same.png", "b"),
  ]);
  expect(screen.getByText(/0 of 2 ready/)).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain("Identical photo");
});
it("accepts a multi-file drop without starting recognition before confirmation", async () => {
  mount();
  const drop = screen.getByRole("button", { name: "Choose photos or drop them here" }) as HTMLButtonElement;
  await waitFor(() => expect(drop.disabled).toBe(false));
  fireEvent.drop(drop, { dataTransfer: { files: [file("사진.png"), file("café.png")] } });
  await screen.findByText(/0 of 2 ready/);
  expect(api.createCapture).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/2 of 2 ready/);
  expect(vi.mocked(api.createCapture).mock.calls.map((call) => call[1].name)).toEqual(["사진.png", "café.png"]);
});
it("requires store currency to load and recovers from a project API error", async () => {
  vi.mocked(api.getProject).mockRejectedValueOnce(new Error("Store offline"));
  mount();
  const retry = await screen.findByRole("button", { name: "Retry store" });
  expect((screen.getByRole("button", { name: "Choose photos or drop them here" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Shelf photo files"), { target: { files: [file("shelf.png")] } });
  expect(api.createCapture).not.toHaveBeenCalled();
  expect(screen.getByText(/0 of 0 ready/)).toBeTruthy();
  vi.mocked(api.getProject).mockResolvedValue({ metadata: { currency: "KRW" } } as Awaited<ReturnType<typeof api.getProject>>);
  fireEvent.click(retry);
  await choose([file("shelf.png")]);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/1 of 1 ready/);
  expect(vi.mocked(api.createCapture).mock.calls[0]![2]?.currency).toBe("KRW");
});
it("rejects empty and unsupported files and bounds a selection to twenty", async () => {
  mount();
  await choose([
    new File([], "empty.png", { type: "image/png" }),
    new File(["pdf"], "plan.pdf", { type: "application/pdf" }),
    ...Array.from({ length: 21 }, (_, i) => file(`${i}.png`)),
  ]);
  expect(screen.getByText(/0 of 20 ready/)).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toMatch(
    /empty[\s\S]*JPEG[\s\S]*Queue limit/,
  );
  expect(api.createCapture).not.toHaveBeenCalled();
});
it("pauses after the current recognition and resumes the remaining photo", async () => {
  const pending = deferred<api.CaptureView>();
  vi.mocked(api.getCapture).mockReturnValueOnce(pending.promise);
  mount();
  await choose([file("1.png"), file("2.png")]);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await waitFor(() => expect(api.getCapture).toHaveBeenCalledTimes(1));
  fireEvent.click(
    screen.getByRole("button", { name: "Pause after current photo" }),
  );
  pending.resolve({ status, result: null });
  await screen.findByText(/1 of 2 ready.*Queue stopped/);
  expect(api.createCapture).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/2 of 2 ready/);
  expect(api.createCapture).toHaveBeenCalledTimes(2);
});
it("removes an unsent photo while another is processing", async () => {
  const pending = deferred<api.CaptureView>();
  vi.mocked(api.getCapture).mockReturnValueOnce(pending.promise);
  mount();
  await choose([file("1.png"), file("2.png")]);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await waitFor(() => expect(api.getCapture).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole("button", { name: "Remove from queue" }));
  pending.resolve({ status, result: null });
  await screen.findByText(/1 of 1 ready/);
  expect(api.createCapture).toHaveBeenCalledTimes(1);
});
it("retries an uncertain upload with identical identity and fixed settings", async () => {
  vi.mocked(api.createCapture).mockRejectedValueOnce(
    new Error("Connection lost"),
  );
  mount();
  await choose([file("photo.png")]);
  expect(
    (screen.getByLabelText("Prices in") as HTMLSelectElement).disabled,
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Retry this photo" }),
  );
  await screen.findByText(/1 of 1 ready/);
  expect(vi.mocked(api.createCapture).mock.calls[0]![2]).toEqual(
    vi.mocked(api.createCapture).mock.calls[1]![2],
  );
});
it("retries polling without uploading the accepted photo again", async () => {
  vi.mocked(api.getCapture).mockRejectedValueOnce(new Error("Status offline"));
  mount();
  await choose([file("photo.png")]);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Retry this photo" }),
  );
  await screen.findByText(/1 of 1 ready/);
  expect(api.createCapture).toHaveBeenCalledTimes(1);
  expect(api.getCapture).toHaveBeenCalledTimes(2);
});
it("blocks a new recognition attempt while another accepted photo has an unknown status", async () => {
  vi.mocked(api.getCapture)
    .mockResolvedValueOnce({
      status: { ...status, status: "failed", error: "Model unavailable" },
      result: null,
    })
    .mockRejectedValueOnce(new Error("Status offline"));
  mount();
  await choose([file("1.png"), file("2.png"), file("3.png")]);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByRole("button", { name: "Retry this photo" });
  const newAttempt = screen.getByRole("button", {
    name: "Retry recognition (new attempt)",
  }) as HTMLButtonElement;
  expect(newAttempt.disabled).toBe(true);
  fireEvent.click(newAttempt);
  expect(api.createCapture).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole("button", { name: "Retry this photo" }));
  await screen.findByText(/2 of 3 ready.*Queue stopped/);
  expect(api.createCapture).toHaveBeenCalledTimes(3);
  expect(newAttempt.disabled).toBe(false);
});
it("starts a new identity only after an explicit retry of failed recognition", async () => {
  vi.mocked(api.getCapture).mockResolvedValueOnce({
    status: { ...status, status: "failed", error: "Model unavailable" },
    result: null,
  });
  mount();
  await choose([file("photo.png")]);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Retry recognition (new attempt)",
    }),
  );
  await screen.findByText(/1 of 1 ready/);
  expect(vi.mocked(api.createCapture).mock.calls[0]![2].request_id).not.toBe(
    vi.mocked(api.createCapture).mock.calls[1]![2].request_id,
  );
});
it("aborts local waiting and starts no later files after unmount", async () => {
  const pending = deferred<api.CaptureStatus>();
  vi.mocked(api.createCapture).mockReturnValueOnce(pending.promise);
  const view = mount();
  await choose([file("1.png"), file("2.png")]);
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await waitFor(() => expect(api.createCapture).toHaveBeenCalledTimes(1));
  const signal = vi.mocked(api.createCapture).mock.calls[0]![3]!;
  view.unmount();
  pending.resolve(status);
  await waitFor(() => expect(signal.aborted).toBe(true));
  expect(api.createCapture).toHaveBeenCalledTimes(1);
  expect(accepted).not.toHaveBeenCalled();
});
it("keeps the selected currency even if project metadata refreshes before starting", async () => {
  mount();
  await choose([file("photo.png")]);
  qc.setQueryData(["projects", "p"], { metadata: { currency: "KRW" } });
  await waitFor(() =>
    expect(
      qc.getQueryData<{ metadata: { currency: string } }>(["projects", "p"])!
        .metadata.currency,
    ).toBe("KRW"),
  );
  fireEvent.click(screen.getByRole("button", { name: "Start / resume queue" }));
  await screen.findByText(/1 of 1 ready/);
  expect(vi.mocked(api.createCapture).mock.calls[0]![2].currency).toBe("USD");
});
it("enforces the total byte budget independently from the per-file maximum", async () => {
  const big = Array.from({ length: 4 }, (_, i) => file(`${i}.png`));
  for (const f of big)
    Object.defineProperty(f, "size", { value: 25 * 1024 * 1024 });
  mount();
  await choose([...big, file("extra.png")]);
  expect(screen.getByText(/0 of 4 ready/)).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain("100 MB");
});

it("says a model is needed before reading products, unless the queue only finds them", async () => {
  vi.mocked(api.getModelSetup).mockResolvedValue({ ...setupWithKey, cloud_providers: [] });
  mount();
  expect(await screen.findByTestId("needs-model")).toBeTruthy();
  fireEvent.change(screen.getByRole("combobox", { name: "Read products with" }), { target: { value: "none" } });
  expect(screen.queryByTestId("needs-model")).toBeNull();
});
