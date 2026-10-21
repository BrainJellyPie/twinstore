// @vitest-environment jsdom
import { StrictMode, useEffect } from "react";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useQueuedStart } from "../useQueuedStart";

afterEach(cleanup);

function Starter({ start, value }: { start: (v: string) => void; value: string }) {
  const queue = useQueuedStart(start);
  useEffect(() => { queue(value); }, [queue, value]);
  return null;
}

it("starts a request queued from a mount effect once, even under StrictMode", async () => {
  const start = vi.fn();
  const view = render(<StrictMode><Starter start={start} value="first" /></StrictMode>);
  await waitFor(() => expect(start).toHaveBeenCalledWith("first"));
  expect(start).toHaveBeenCalledTimes(1);
  view.rerender(<StrictMode><Starter start={start} value="second" /></StrictMode>);
  await waitFor(() => expect(start).toHaveBeenCalledWith("second"));
  expect(start).toHaveBeenCalledTimes(2);
});
