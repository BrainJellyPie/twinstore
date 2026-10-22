// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { TemplatePicker } from "../components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE } from "../templateOptions";
import type { Rack } from "@/shared/types/domain";

vi.mock("@/shared/api/client", () => ({ getStoreTemplates: vi.fn(), previewStoreTemplate: vi.fn() }));
let client: QueryClient;
afterEach(() => { cleanup(); client?.clear(); vi.resetAllMocks(); useLocale.getState().setLocale("en"); });

it.each([
  ["en", "Checkout counters:", "Operating hours · Open days: 1"],
  ["es", "Cajas:", "Horario · Días de apertura: 1"],
  ["fr", "Caisses :", "Horaires · Jours d’ouverture : 1"],
] as const)("uses count-neutral summaries for zero, one and several counters in %s", async (locale, counterLabel, hoursLabel) => {
  useLocale.getState().setLocale(locale);
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(api.getStoreTemplates).mockResolvedValue([{ id: "urban_cvs", name: "Original", description: "Original", store_type: "convenience", grid: [12, 10], racks: 0, skus: 0, open_hours: [9, 18], closed_days: [2, 3, 4, 5, 6, 7], default_style: "aisles", default_design: "classic", default_dining_tables: 0 }]);
  for (const count of [0, 1, 2]) {
    const racks: Rack[] = Array.from({ length: count }, (_, i) => ({ id: `counter-${i}`, rack_name: `Original ${i}`, rack_desc: "", rack_decoration_desc: "", levels: 1, dwell_min: 0, dwell_max: 0, locked_faces: [], type: "counter", position: [i + 2, 1], shape: [[1]], rotation: 0, slots: [] }));
    vi.mocked(api.previewStoreTemplate).mockResolvedValue({ id: "preview", name: "Original", type: "store", grid_size: [12, 10], racks, weekly_schedule: [] });
    render(<QueryClientProvider client={client}><TemplatePicker value={DEFAULT_TEMPLATE_CHOICE} onChange={vi.fn()} /></QueryClientProvider>);
    await screen.findByText(`${counterLabel} ${count}`);
    expect(screen.getByText(hoursLabel)).toBeTruthy();
    cleanup(); client.clear();
  }
});
