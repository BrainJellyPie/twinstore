import { afterEach, expect, it, vi } from "vitest";

import { createCapture, createStore, deleteCapture, deleteEdit, deletePackage, importFloorPlan, readReceipts, regeneratePersona, uploadPackage } from "../client";
import { ApiError } from "../errors";
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

it.each([
  [{ detail: { code: "setup_running", reason: "running", message: "This layout is running a simulation; wait for it to finish.", details: {} } }, "This layout is running a simulation; wait for it to finish."],
  [{ detail: { code: "setup_running", message: "  " } }, "409 Conflict"],
  [{ detail: { code: "setup_running", message: 3 } }, "409 Conflict"],
])("shows the message of structured setup errors and keeps the status for %j", async (body, expected) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 409, statusText: "Conflict" })));
  const error: unknown = await regeneratePersona("project", "setup").catch((cause: unknown) => cause);
  expect(error).toBeInstanceOf(ApiError);
  expect((error as ApiError).message).toBe(expected);
  expect((error as ApiError).status).toBe(409);
});

it("reads structured messages in the interview client too", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: { code: "not_found", message: "Shopper left the store" } }), { status: 404, statusText: "Not Found" })));
  await expect(askShopper("project", "run", "shopper", "Question", "")).rejects.toThrow("Shopper left the store");
});

it("uploads a package as multipart form data and reads the server's reason on failure", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "not an image: photo.png" }), { status: 400, statusText: "Bad Request" }));
  vi.stubGlobal("fetch", fetch);
  await expect(uploadPackage("project", file)).rejects.toThrow(new ApiError("not an image: photo.png", 400));
  const init = fetch.mock.calls[0]![1] as RequestInit;
  expect(init.body).toBeInstanceOf(FormData);
  expect(new Headers(init.headers).has("Content-Type")).toBe(false);
});

it.each([
  ["package", () => deletePackage("project", "pkg")],
  ["capture", () => deleteCapture("project", "cap")],
  ["counterfactual", () => deleteEdit("project", "cap", "edit")],
])("explains a rejected %s delete", async (_, run) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "still in use" }), { status: 409, statusText: "Conflict" })));
  const error = await run().catch((e: unknown) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ message: "still in use", status: 409 });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 409, statusText: "Conflict" })));
  await expect(run()).rejects.toThrow("Delete failed (HTTP 409)");
});
