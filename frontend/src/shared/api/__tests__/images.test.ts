import { afterEach, expect, it, vi } from "vitest";

import { uploadSkuImages } from "../images";

afterEach(() => vi.unstubAllGlobals());

it.each(["tea", "A/B", "../tea", ".", "..", "%2F", "%25", "coffee 100%", "tea?size=1#box", "차/대형", ""])(
  "preserves SKU %j when uploading a photo",
  async (sku) => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ sku, url: "/photo" })));
    vi.stubGlobal("fetch", fetch);

    const result = await uploadSkuImages("Project-A", { [sku]: { bytes: new Uint8Array([1, 2, 3]), extension: "png" } });

    expect(result).toEqual([{ sku, url: "/photo" }]);
    const [address, options] = fetch.mock.calls[0]!;
    const url = new URL(address as string, "http://localhost");
    expect(url.pathname).toBe("/api/projects/Project-A/sku-images");
    expect(url.searchParams.get("sku")).toBe(sku);
    expect(options).toEqual({ method: "POST", body: expect.any(FormData) });
  },
);
