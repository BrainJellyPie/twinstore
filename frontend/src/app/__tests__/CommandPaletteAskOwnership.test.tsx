// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render as renderUi,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { useLocale } from "@/shared/i18n/i18n";
import { useAssistStore } from "@/stores/assistStore";
import { CommandPalette } from "../CommandPalette";
import { useCommandPalette } from "../commandPalette";
const state = vi.hoisted(() => ({
  navigate: vi.fn(),
  listeners: new Set<() => void>(),
  pathname: "/projects/alpha",
  projects: [
    {
      project_id: "alpha",
      name: "Alpha",
      store_type: "convenience",
      status: "Simulated",
    },
    {
      project_id: "beta",
      name: "Beta",
      store_type: "convenience",
      status: "Simulated",
    },
  ],
}));
vi.mock("@tanstack/react-router", async () => {
  const { useSyncExternalStore } = await import("react");
  return {
    useNavigate: () => state.navigate,
    useLocation: () => ({
      pathname: useSyncExternalStore(
        (listener) => {
          state.listeners.add(listener);
          return () => {
            state.listeners.delete(listener);
          };
        },
        () => state.pathname,
      ),
    }),
  };
});
vi.mock("@/shared/queries/useProjects", () => ({
  useProjects: () => ({ data: state.projects }),
}));
vi.mock("../theme", () => ({
  useTheme: () => ({ theme: "dark", setTheme: vi.fn() }),
}));
vi.mock("../launcher", () => ({
  useLauncher: () => false,
  quitLauncher: vi.fn(),
}));
vi.mock("@/shared/api/client", async (original) => ({
  ...(await original<typeof import("@/shared/api/client")>()),
  routeAssist: vi.fn(),
}));
Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
  configurable: true,
  value: vi.fn(),
});
type Route = Awaited<ReturnType<typeof api.routeAssist>>;
function deferred() {
  let resolve!: (v: Route) => void;
  let reject!: (e: Error) => void;
  const promise = new Promise<Route>((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
}
const render = (ui: ReactElement) => {
  const client = new QueryClient();
  return renderUi(ui, { wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });
};
beforeEach(() => {
  state.pathname = "/projects/alpha";
  useLocale.getState().setLocale("en");
  useCommandPalette.setState({ open: true });
});
afterEach(() => {
  cleanup();
  useCommandPalette.setState({ open: false });
  useAssistStore.setState({ pending: null });
  vi.resetAllMocks();
});
function type(text: string) {
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: text } });
  return input;
}
function request(text = "Would a discount sell more tea?") {
  fireEvent.keyDown(type(text), { key: "Enter" });
}
const changes = ["query", "project", "close"] as const;
for (const outcome of ["success", "failure", "none"] as const) {
  it.each(changes)(
    `ignores an old ${outcome} after changing %s`,
    async (change) => {
      const pending = deferred();
      vi.mocked(api.routeAssist).mockReturnValue(pending.promise);
      render(<CommandPalette />);
      request();
      await waitFor(() => expect(api.routeAssist).toHaveBeenCalledTimes(1));
      if (change === "query") type("Would a new price sell more coffee?");
      if (change === "project") {
        act(() => {
          state.pathname = "/projects/beta";
          state.listeners.forEach((listener) => listener());
        });
      }
      if (change === "close") {
        act(() => useCommandPalette.setState({ open: false }));
        act(() => useCommandPalette.setState({ open: true }));
        type("Would a new price sell more coffee?");
      }
      await act(async () => {
        if (outcome === "failure")
          pending.reject(new Error("Old routing failure"));
        else
          pending.resolve({
            destination: outcome === "none" ? "none" : "ab_test",
            reason: "",
          });
        await pending.promise.catch(() => {});
      });
      expect(state.navigate).not.toHaveBeenCalled();
      expect(useAssistStore.getState().pending).toBeNull();
      expect(useCommandPalette.getState().open).toBe(true);
      expect(screen.queryByText("Old routing failure")).toBeNull();
      expect(screen.queryByText(/TwinStore cannot set that up yet/)).toBeNull();
    },
  );
}
it("routes only the latest question when replies arrive in reverse order", async () => {
  const old = deferred(),
    current = deferred();
  vi.mocked(api.routeAssist)
    .mockReturnValueOnce(old.promise)
    .mockReturnValueOnce(current.promise);
  render(<CommandPalette />);
  request();
  await waitFor(() => expect(api.routeAssist).toHaveBeenCalledTimes(1));
  request("Would oat milk preferences vary by price?");
  await waitFor(() => expect(api.routeAssist).toHaveBeenCalledTimes(2));
  await act(async () => {
    current.resolve({ destination: "conjoint", reason: "" });
    await current.promise;
  });
  expect(useAssistStore.getState().pending).toMatchObject({
    destination: "conjoint",
    text: "Would oat milk preferences vary by price?",
  });
  await act(async () => {
    old.resolve({ destination: "area", reason: "" });
    await old.promise;
  });
  expect(state.navigate).toHaveBeenCalledTimes(1);
  expect(useAssistStore.getState().pending?.destination).toBe("conjoint");
});
it.each([
  ["ko", "콜라할인을비교해줘"],
  ["zh", "比较可乐降价效果"],
  ["ja", "コーラの値下げを比べて"],
] as const)(
  "offers requests written without spaces in %s",
  async (locale, text) => {
    useLocale.getState().setLocale(locale);
    vi.mocked(api.routeAssist).mockResolvedValue({
      destination: "ab_test",
      reason: "",
    });
    render(<CommandPalette />);
    request(text);
    await waitFor(() =>
      expect(api.routeAssist).toHaveBeenCalledWith({ text, has_run: true }),
    );
  },
);
it("keeps a 500-code-point request valid without splitting a supplementary character", async () => {
  vi.mocked(api.routeAssist).mockResolvedValue({
    destination: "none",
    reason: "",
  });
  render(<CommandPalette />);
  const value = "Compare tea " + "a".repeat(487) + "🛒";
  const input = type(value + "x") as HTMLInputElement;
  expect(input.value).toBe(value);
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() =>
    expect(api.routeAssist).toHaveBeenCalledWith({
      text: value,
      has_run: true,
    }),
  );
});
it("keeps a failed current question available for retry", async () => {
  vi.mocked(api.routeAssist)
    .mockRejectedValueOnce(new Error("Routing unavailable"))
    .mockResolvedValueOnce({ destination: "ab_test", reason: "" });
  render(<CommandPalette />);
  request();
  await screen.findByText("Routing unavailable");
  fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" });
  await waitFor(() => expect(state.navigate).toHaveBeenCalledTimes(1));
  expect(api.routeAssist).toHaveBeenCalledTimes(2);
});
