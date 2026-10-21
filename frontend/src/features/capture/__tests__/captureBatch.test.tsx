// @vitest-environment jsdom
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import type { CaptureBatchPreview } from "@/shared/api/captureBatch";
import { CaptureBatch } from "../CaptureBatch";
import { useSimulationStore } from "@/stores/simulationStore";
const { navigate } = vi.hoisted(() => ({ navigate: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => navigate }));
vi.mock("@/shared/api/client", async (original) => ({
  ...(await original<typeof import("@/shared/api/client")>()),
  getSetups: vi.fn(),
}));
const fetchMock = vi.fn<typeof fetch>();
let qc: QueryClient;
const captures: api.CaptureStatus[] = ["a", "b"].map((id) => ({
  capture_id: id,
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
  image_name: `${id}.jpg`,
  image_size: [200, 200],
  created_at: "",
  finished_at: "",
  items: 1,
  facings: 2,
  gaps: 0,
  levels: 1,
  applied_setup_ids: [],
}));
const preview: CaptureBatchPreview = {
  source_sha256: "a".repeat(64),
  store: {
    id: "s",
    name: "Base",
    type: "convenience",
    grid_size: [12, 12],
    weekly_schedule: [],
    racks: [],
  },
  rack_ids: ["rack1", "rack2"],
  placed_items: 2,
  placed_facings: 4,
  requested_facings: 4,
  reduced_facings: 0,
  dropped: [],
  notes: [],
  estimated_prices: 1,
  unrecognized_items: 1,
};
const saved = {
  setup_id: "setup_new",
  rack_ids: ["rack1", "rack2"],
  placed_items: 2,
  placed_facings: 4,
  notes: [],
};
beforeEach(() => {
  qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(api.getSetups).mockResolvedValue([
    {
      id: "base",
      name: "Base",
      status: "draft",
      parentId: null,
      runId: null,
      memo: "",
      created_at: "",
      updated_at: "",
    },
  ]);
});
afterEach(() => {
  cleanup();
  qc.clear();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  fetchMock.mockReset();
  useSimulationStore.getState().reset();
});
function mount(items = captures) {
  return render(
    <QueryClientProvider client={qc}>
      <CaptureBatch projectId="p" captures={items} onReview={vi.fn()} />
    </QueryClientProvider>,
  );
}
async function select() {
  fireEvent.click(
    screen.getByRole("button", { name: "Combine reviewed shelf photos" }),
  );
  await screen.findByRole("option", { name: "Base" });
  fireEvent.click(
    screen.getByRole("button", { name: "Select first 20 ready photos" }),
  );
}
async function review() {
  await select();
  fireEvent.click(
    screen.getByRole("button", { name: "Preview combined layout" }),
  );
  await screen.findByRole("button", { name: "Save combined draft" });
}
it("selects two photos, previews a floor plan, saves one draft and opens it only on request", async () => {
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify(preview)))
    .mockResolvedValueOnce(new Response(JSON.stringify(saved)));
  mount();
  await review();
  expect(screen.getByText(/2 new racks/)).toBeTruthy();
  expect(screen.getByText(/1 product entries have estimated/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Save combined draft" }));
  await screen.findByText(/Combined draft saved/);
  expect(JSON.parse(fetchMock.mock.calls[0]![1]!.body as string)).toEqual({
    capture_ids: ["a", "b"],
    setup_id: "base",
  });
  const body = JSON.parse(fetchMock.mock.calls[1]![1]!.body as string);
  expect(body.source_sha256).toBe(preview.source_sha256);
  expect(body.request_id).toMatch(/^[0-9a-f]{32}$/);
  expect(navigate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Open combined layout" }));
  expect(navigate).toHaveBeenCalledWith({
    to: "/projects/$pid",
    params: { pid: "p" },
  });
  expect(useSimulationStore.getState().selectedSetupId).toBe("setup_new");
});
it("keeps the reviewed base and saved link when the refreshed list puts the new draft first", async () => {
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify(preview)))
    .mockResolvedValueOnce(new Response(JSON.stringify(saved)));
  mount();
  await review();
  vi.mocked(api.getSetups).mockResolvedValue([
    {
      id: "setup_new",
      name: "New draft",
      status: "draft",
      parentId: "base",
      runId: null,
      memo: "",
      created_at: "",
      updated_at: "",
    },
    {
      id: "base",
      name: "Base",
      status: "draft",
      parentId: null,
      runId: null,
      memo: "",
      created_at: "",
      updated_at: "",
    },
  ]);
  fireEvent.click(screen.getByRole("button", { name: "Save combined draft" }));
  await waitFor(() => expect(api.getSetups).toHaveBeenCalledTimes(2));
  expect(
    await screen.findByRole("button", { name: "Open combined layout" }),
  ).toBeTruthy();
  expect(
    (screen.getByLabelText("Base layout") as HTMLSelectElement).value,
  ).toBe("base");
});
it("retries an uncertain save with exactly the same request identity", async () => {
  fetchMock
    .mockResolvedValueOnce(new Response(JSON.stringify(preview)))
    .mockRejectedValueOnce(new Error("Connection lost"))
    .mockResolvedValueOnce(new Response(JSON.stringify(saved)));
  mount();
  await review();
  fireEvent.click(screen.getByRole("button", { name: "Save combined draft" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Retry saving this draft" }),
  );
  await screen.findByText(/Combined draft saved/);
  expect(fetchMock.mock.calls[1]![1]!.body).toBe(
    fetchMock.mock.calls[2]![1]!.body,
  );
});
it("requires a new preview when changing photos and blocks partial placement", async () => {
  fetchMock.mockResolvedValueOnce(
    new Response(
      JSON.stringify({ ...preview, dropped: ["Too many products"] }),
    ),
  );
  mount();
  await review();
  expect(
    (
      screen.getByRole("button", {
        name: "Save combined draft",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  expect(screen.getByRole("alert").textContent).toContain("Too many products");
  fireEvent.click(screen.getAllByRole("checkbox")[0]!);
  expect(
    screen.queryByRole("button", { name: "Save combined draft" }),
  ).toBeNull();
});
it("bounds selection to twenty ready photos and excludes failed, empty and pending ones", async () => {
  const many = Array.from({ length: 25 }, (_, i) => ({
    ...captures[0]!,
    capture_id: `c${i}`,
    image_name: `c${i}.jpg`,
  }));
  many[0]!.status = "pending";
  many[1]!.status = "failed";
  many[2]!.items = 0;
  mount(many);
  await select();
  expect(screen.getByText(/20 selected/)).toBeTruthy();
  const boxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
  expect(boxes.filter((b) => b.checked)).toHaveLength(20);
  expect(boxes.slice(0, 3).every((b) => b.disabled)).toBe(true);
  expect(boxes[24]!.disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Clear selection" }));
  expect(screen.getByText(/0 selected/)).toBeTruthy();
});
it("locks changes during requests and ignores completion after unmount", async () => {
  let finish!: (r: Response) => void;
  fetchMock.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const view = mount();
  await select();
  fireEvent.click(
    screen.getByRole("button", { name: "Preview combined layout" }),
  );
  await waitFor(() =>
    expect(
      (screen.getByLabelText("Base layout") as HTMLSelectElement).disabled,
    ).toBe(true),
  );
  expect(
    (screen.getAllByRole("checkbox")[0] as HTMLInputElement).disabled,
  ).toBe(true);
  const pending = qc.getMutationCache().getAll()[0]!;
  view.unmount();
  finish(new Response(JSON.stringify(preview)));
  await waitFor(() => expect(pending.state.status).toBe("success"));
  expect(navigate).not.toHaveBeenCalled();
  expect(useSimulationStore.getState().selectedSetupId).toBeNull();
});
it("retains the selection after a preview failure and supports a fresh preview", async () => {
  fetchMock
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "These shelves do not fit" }), {
        status: 409,
      }),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify(preview)));
  mount();
  await select();
  fireEvent.click(
    screen.getByRole("button", { name: "Preview combined layout" }),
  );
  expect((await screen.findByRole("alert")).textContent).toContain(
    "do not fit",
  );
  expect(screen.getByText(/2 selected/)).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: "Preview combined layout" }),
  );
  await screen.findByRole("button", { name: "Save combined draft" });
});
it("explains missing layouts and recovers from layout loading failure", async () => {
  vi.mocked(api.getSetups)
    .mockRejectedValueOnce(new Error("Offline"))
    .mockResolvedValueOnce([]);
  mount();
  fireEvent.click(
    screen.getByRole("button", { name: "Combine reviewed shelf photos" }),
  );
  fireEvent.click(await screen.findByRole("button", { name: "Retry layouts" }));
  expect(await screen.findByText(/Create a base layout/)).toBeTruthy();
  expect(
    (
      screen.getByRole("button", {
        name: "Preview combined layout",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("requires explicit facing reduction acceptance and freezes it for uncertain retries", async () => {
  fetchMock
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          ...preview,
          requested_facings: 26,
          reduced_facings: 22,
        }),
      ),
    )
    .mockRejectedValueOnce(new Error("Connection lost"))
    .mockResolvedValueOnce(new Response(JSON.stringify(saved)));
  mount();
  await review();
  const button = screen.getByRole("button", {
    name: "Save combined draft",
  }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  const accept = screen.getByRole("checkbox", {
    name: /Accept 4 facings instead of 26/,
  }) as HTMLInputElement;
  fireEvent.click(accept);
  expect(button.disabled).toBe(false);
  fireEvent.click(button);
  const retry = await screen.findByRole("button", {
    name: "Retry saving this draft",
  });
  expect(accept.disabled).toBe(true);
  fireEvent.click(retry);
  await screen.findByText(/Combined draft saved/);
  expect(
    JSON.parse(fetchMock.mock.calls[1]![1]!.body as string)
      .allow_reduced_facings,
  ).toBe(true);
  expect(fetchMock.mock.calls[1]![1]!.body).toBe(
    fetchMock.mock.calls[2]![1]!.body,
  );
});
