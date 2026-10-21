import { afterEach, expect, it, vi } from "vitest";

import { createCapture, createStore, importFloorPlan, readReceipts } from "../client";
import { askShopper } from "../interview";
import { previewShelf } from "../marketing";

afterEach(() => vi.unstubAllGlobals());

const file = new File(["photo"], "photo.png", { type: "image/png" });
const requests = [
  { name: "store creation", run: () => createStore({ name: "Test shop", description: "", address: "12 Market Street", store_type: "convenience", customer_profile: "Local residents", weekly_schedule: [] }, null) },
  { name: "shopper interview", run: () => askShopper("project", "run", "shopper", "", "") },
  { name: "shelf preview", run: () => previewShelf("project", { setup_id: "setup", rack_id: "rack", target_sku: "tea", changes: [] }) },
  { name: "capture upload", run: () => createCapture("project", file, { detector: "classic", model: "none", currency: "USD", rack_type: "shelf" }) },
  { name: "floorplan import", run: () => importFloorPlan("project", file, { reader: "classic" }) },
  { name: "receipt upload", run: () => readReceipts("project", [file], { setupId: "setup" }) },
];

it.each(requests)("shows readable field validation errors for $name", async ({ run }) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [
    { loc: ["body", "changes", 0, "price"], msg: "Input should be greater than or equal to 0", input: -1 },
    { loc: ["body", "name"], msg: "String should have at least 1 character", input: "" },
  ] }), { status: 422, statusText: "Unprocessable Entity" })));
  await expect(run()).rejects.toThrow("changes.0.price: Input should be greater than or equal to 0; name: String should have at least 1 character");
});

it.each([
  [JSON.stringify({ detail: "Project is locked" }), "Project is locked"],
  ["Service unavailable", "Service unavailable"],
  ["null", "503 Service Unavailable"],
  [JSON.stringify({ detail: {} }), "503 Service Unavailable"],
  [JSON.stringify({ detail: [] }), "503 Service Unavailable"],
  ["", "503 Service Unavailable"],
])("keeps useful errors and falls back safely for %s", async (body, expected) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status: 503, statusText: "Service Unavailable" })));
  await expect(askShopper("project", "run", "shopper", "Question", "")).rejects.toThrow(expected);
});

it.each([
  [JSON.stringify({ detail: "Store creation is temporarily unavailable" }), "Store creation is temporarily unavailable"],
  ["Service unavailable", "Service unavailable"],
  ["", "Failed to create store (HTTP 503)"],
  ["null", "Failed to create store (HTTP 503)"],
  [JSON.stringify({ detail: {} }), "Failed to create store (HTTP 503)"],
])("keeps store-creation errors readable for %j", async (body, expected) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status: 503 })));
  await expect(createStore({ name: "Test shop", description: "", address: "12 Market Street", store_type: "convenience", customer_profile: "Local residents", weekly_schedule: [] }, null)).rejects.toThrow(expected);
});
