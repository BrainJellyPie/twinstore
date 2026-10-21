import { afterEach, expect, it, vi } from "vitest";
import { previewStoreTemplate } from "../client";

afterEach(() => vi.unstubAllGlobals());

it("sends structured reserved areas without source links or manual notes to the preview API", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ racks: [] })));
  vi.stubGlobal("fetch", fetch);
  const reserved_areas = [{ label: "Consultation & pickup", x: 2, y: 4, width: 3, height: 2 }];
  await previewStoreTemplate({ template_id: "community_pharmacy", seed: 7, currency: "JPY", reserved_areas,
    name: "My store", source_setup_id: "setup_original", requirements: "Add warm lighting" });
  expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/store-templates\/preview$/), expect.objectContaining({
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template_id: "community_pharmacy", seed: 7, currency: "JPY", reserved_areas }),
  }));
});
