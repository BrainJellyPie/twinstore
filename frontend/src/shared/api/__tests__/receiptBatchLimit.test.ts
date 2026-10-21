import { afterEach, expect, it, vi } from "vitest";

import { readReceipts } from "../client";

afterEach(() => vi.unstubAllGlobals());

it.each([100, 101])("checks the review limit before uploading %i receipt photos", async (count) => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ receipts: [] })));
  vi.stubGlobal("fetch", fetch);
  const photos = Array.from({ length: count }, (_, i) => new File(["photo"], `receipt-${i}.png`, { type: "image/png" }));

  if (count > 100) {
    await expect(readReceipts("project", photos, { runId: "run" })).rejects.toThrow("100");
    expect(fetch).not.toHaveBeenCalled();
  } else {
    await expect(readReceipts("project", photos, { runId: "run" })).resolves.toEqual({ receipts: [] });
    expect(fetch).toHaveBeenCalledOnce();
    const options = fetch.mock.calls[0]?.[1] as RequestInit;
    expect((options.body as FormData).getAll("photos")).toHaveLength(count);
  }
});
