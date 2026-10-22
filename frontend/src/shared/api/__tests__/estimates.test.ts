import { afterEach, expect, it, vi } from "vitest";
import { confirmGeneration, estimateRun, getScenarios, previewScenario, startRun, type RunOptions, type Scenario } from "../client";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(body: unknown) {
  const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify(body)));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

it("estimates a run with exactly the body that starts it", async () => {
  const fetch = stubFetch({});
  const options: RunOptions = { engine_type: "pattern_intent_impulse", seed: 3, max_customers: 300, preview: true };
  await estimateRun("p", "s", options);
  await startRun("p", "s", options);
  const [[estimateUrl, estimate], [runUrl, run]] = fetch.mock.calls as [[string, RequestInit], [string, RequestInit]];
  expect(estimateUrl).toMatch(/\/api\/projects\/p\/runs\/estimate$/);
  expect(runUrl).toMatch(/\/api\/projects\/p\/runs$/);
  expect(estimate.method).toBe("POST");
  expect(estimate.body).toBe(run.body);
  expect(JSON.parse(estimate.body as string)).toEqual({ setup_id: "s", ...options });
});

it("posts the generation choice", async () => {
  const fetch = stubFetch({ status: "running" });
  await confirmGeneration("p", "s", "g", "sample");
  expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/projects\/p\/setups\/s\/generations\/g\/confirm$/),
    expect.objectContaining({ method: "POST", body: JSON.stringify({ choice: "sample" }) }));
});

it("asks for scenario effects at a layout's store format only when one is given", async () => {
  const fetch = stubFetch([]);
  await getScenarios();
  await getScenarios({ projectId: "p 1", setupId: "s" });
  await previewScenario({ id: "custom" } as Scenario, { projectId: "p", setupId: "s" });
  await previewScenario({ id: "custom" } as Scenario);
  const urls = fetch.mock.calls.map(([url]) => String(url));
  expect(urls[0]).toMatch(/\/api\/scenarios$/);
  expect(urls[1]).toMatch(/\/api\/scenarios\?project_id=p\+1&setup_id=s$/);
  expect(urls[2]).toMatch(/\/api\/scenarios\/preview\?project_id=p&setup_id=s$/);
  expect(urls[3]).toMatch(/\/api\/scenarios\/preview$/);
});
