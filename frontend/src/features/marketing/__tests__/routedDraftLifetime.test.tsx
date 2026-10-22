// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as marketing from "@/shared/api/marketing";
import { useAssistStore, type AssistDestination } from "@/stores/assistStore";
import { MarketingPage } from "../MarketingPage";
vi.mock("@/shared/api/client", async (original) => ({
  ...(await original<typeof import("@/shared/api/client")>()),
  getProject: vi.fn(),
  getSetup: vi.fn(),
  getModels: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/shared/api/marketing", async (original) => ({
  ...(await original<typeof import("@/shared/api/marketing")>()),
  getMarketingInfo: vi.fn().mockResolvedValue({ currency: "USD" }),
  listExperiments: vi.fn().mockResolvedValue([]),
  listSurveys: vi.fn().mockResolvedValue([]),
  listPitches: vi.fn().mockResolvedValue([]),
  listShelfTests: vi.fn().mockResolvedValue([]),
  listConjoints: vi.fn().mockResolvedValue([]),
  designExperiment: vi.fn(),
  designSurvey: vi.fn(),
  designConjoint: vi.fn(),
  draftPitchScript: vi.fn(),
}));
vi.mock("../hooks", () => ({ usePackages: () => ({ data: [] }) }));
const store = {
  currency: "USD",
  racks: [
    {
      id: "r",
      type: "shelf",
      rack_name: "Drinks",
      rack_desc: "",
      levels: 4,
      slots: [
        {
          block: 0,
          face: "N",
          level: 1,
          items: [
            {
              sku: "tea",
              name: "Tea",
              price: 199,
              regular_price: 0,
              promo: "",
              facings: 1,
            },
          ],
        },
      ],
    },
  ],
};
const setups = [
  { id: "s1", name: "Layout one", status: "draft" },
  { id: "s2", name: "Layout two", status: "draft" },
];
const project = {
  metadata: { currency: "USD" },
  state: { activeSetupId: "s1" },
  setups,
  personas: Array.from({ length: 40 }, (_, i) => ({ id: String(i) })),
};
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.mocked(api.getProject).mockResolvedValue(project as never);
  vi.mocked(api.getSetup).mockImplementation(
    async (_pid, sid) =>
      ({ ...setups.find((s) => s.id === sid), store }) as never,
  );
  vi.mocked(marketing.designSurvey).mockResolvedValue({ name: "Generated survey", stimuli: [], stimulus_names: [], questions: ["appeal"], context: "Brief", reference_price: null, currency: "USD", age_groups: [], genders: [], rationale: "Generated survey rationale", warnings: [] });
  vi.mocked(marketing.designExperiment).mockResolvedValue({
    name: "Generated test",
    engine: "rule",
    rationale: "Generated experiment rationale",
    focus_skus: ["tea"],
    warnings: [],
    variants: [
      {
        name: "Generated variant",
        changes: [{ kind: "discount", sku: "tea", percent: -20 }],
      },
    ],
  });
  vi.mocked(marketing.designConjoint).mockResolvedValue({
    name: "Generated conjoint",
    product: "Generated tea",
    context: "Generated context",
    attributes: [{ name: "Sugar", levels: ["Regular", "Zero"] }],
    prices: [199, 299],
    currency: "USD",
    rationale: "Generated conjoint rationale",
    comparable: [],
  });
  vi.mocked(marketing.draftPitchScript).mockResolvedValue({
    name: "Generated script",
    script: "Generated greeting",
    differs_by: "Generated script rationale",
  });
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((c) => c.clear());
  useAssistStore.setState({ pending: null });
  vi.clearAllMocks();
});
const targets = [
  { destination: "concept_test", tab: "Concept tests", mock: marketing.designSurvey, rationale: "Generated survey rationale" },
  {
    destination: "ab_test",
    tab: "A/B tests",
    mock: marketing.designExperiment,
    rationale: "Generated experiment rationale",
  },
  {
    destination: "conjoint",
    tab: "Conjoint",
    mock: marketing.designConjoint,
    rationale: "Generated conjoint rationale",
  },
  {
    destination: "staff_script",
    tab: "Staff scripts",
    mock: marketing.draftPitchScript,
    rationale: "Generated script rationale",
  },
] as const;
function send(destination: AssistDestination) {
  act(() =>
    useAssistStore
      .getState()
      .send({
        projectId: "p",
        destination,
        text: "Would a different approach sell more tea?",
      }),
  );
}
function mount() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <MarketingPage projectId="p" />
    </QueryClientProvider>,
  );
  return client;
}
for (const navigation of ["tabs", "layout"] as const) {
  it.each(targets)(
    `does not repeat a routed $destination draft after changing ${navigation}`,
    async (target) => {
      send(target.destination);
      const client = mount();
      await screen.findByText(new RegExp(target.rationale));
      expect(target.mock).toHaveBeenCalledTimes(1);
      if (navigation === "tabs") {
        fireEvent.click(
          screen.getByRole("tab", {
            name: target.tab === "Conjoint" ? "A/B tests" : "Conjoint",
          }),
        );
        fireEvent.click(screen.getByRole("tab", { name: target.tab }));
      } else
        fireEvent.change(screen.getByRole("combobox", { name: "Layout" }), {
          target: { value: "s2" },
        });
      await act(async () => {});
      await waitFor(() =>
        expect(client.isFetching() + client.isMutating()).toBe(0),
      );
      expect(target.mock).toHaveBeenCalledTimes(1);
    },
  );
}
it.each(targets)(
  "accepts a second explicit $destination request on the same page",
  async (target) => {
    const client = mount();
    send(target.destination);
    await screen.findByText(new RegExp(target.rationale));
    send(target.destination);
    await waitFor(() => expect(target.mock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(client.isMutating()).toBe(0));
  },
);
it("waits for the project and layout before drafting a routed conjoint", async () => {
  let resolveProject!: (p: api.ProjectDetail) => void;
  vi.mocked(api.getProject).mockReturnValue(
    new Promise((r) => {
      resolveProject = r;
    }),
  );
  send("conjoint");
  mount();
  await act(async () => {});
  expect(marketing.designConjoint).not.toHaveBeenCalled();
  await act(async () => resolveProject(project as never));
  await screen.findByText(/Generated conjoint rationale/);
  expect(marketing.designConjoint).toHaveBeenCalledTimes(1);
  expect(marketing.designConjoint).toHaveBeenCalledWith(
    "p",
    expect.objectContaining({ setup_id: "s1" }),
  );
});

it.each(["project", "layout"])("waits for %s before drafting a routed concept test", async kind => {
  let resolve!: (p: never) => void;
  const pending = new Promise<never>(r => { resolve = r; });
  if (kind === "project") vi.mocked(api.getProject).mockReturnValue(pending);
  else vi.mocked(api.getSetup).mockReturnValue(pending);
  send("concept_test"); const client = mount();
  await act(async () => {});
  if (kind === "layout") await waitFor(() => expect(api.getSetup).toHaveBeenCalled());
  expect(marketing.designSurvey).not.toHaveBeenCalled();
  await act(async () => resolve((kind === "project" ? project : { ...setups[0], store }) as never));
  await screen.findByText(/Generated survey rationale/);
  await waitFor(() => expect(client.isMutating()).toBe(0));
  expect(marketing.designSurvey).toHaveBeenCalledTimes(1);
  expect(marketing.designSurvey).toHaveBeenCalledWith("p", expect.objectContaining({ setup_id: "s1" }));
});
