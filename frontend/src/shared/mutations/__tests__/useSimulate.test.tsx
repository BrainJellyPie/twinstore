// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulate } from "../useSimulate";

vi.mock("@/shared/api/client", () => ({ startRun: vi.fn() }));
afterEach(() => vi.resetAllMocks());

it("refreshes the layouts list and the store list once a run starts", async () => {
  vi.mocked(api.startRun).mockResolvedValue({ run_id: "run" } as Awaited<ReturnType<typeof api.startRun>>);
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const { result } = renderHook(() => useSimulate(), { wrapper });
  await act(async () => { await result.current.mutateAsync({ projectId: "p", setupId: "s" }); });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.runs("p", "s") });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.setups("p"), exact: true });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.projects(), exact: true });
  client.clear();
});
