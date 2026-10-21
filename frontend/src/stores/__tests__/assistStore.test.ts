import { afterEach, expect, it, vi } from "vitest";
import { ASK_TTL_MS, useAssistStore } from "../assistStore";

afterEach(() => { useAssistStore.setState({ pending: null }); vi.useRealTimers(); });

it("hands a routed request only to its project and destination, once", () => {
  useAssistStore.getState().send({ projectId: "p1", destination: "conjoint", text: "Would people pay more for oat milk?" });
  expect(useAssistStore.getState().take("p2", ["conjoint"])).toBeNull();
  expect(useAssistStore.getState().take("p1", ["ab_test", "staff_script"])).toBeNull();
  const ask = useAssistStore.getState().take("p1", ["ab_test", "conjoint"]);
  expect(ask?.text).toBe("Would people pay more for oat milk?");
  expect(useAssistStore.getState().take("p1", ["conjoint"])).toBeNull();
});

it("drops a request nobody picked up in time instead of drafting it later", () => {
  vi.useFakeTimers();
  useAssistStore.getState().send({ projectId: "p1", destination: "run_question", text: "Which shelf sells least?" });
  vi.advanceTimersByTime(ASK_TTL_MS + 1);
  expect(useAssistStore.getState().take("p1", ["run_question"])).toBeNull();
  expect(useAssistStore.getState().pending).toBeNull();
});
