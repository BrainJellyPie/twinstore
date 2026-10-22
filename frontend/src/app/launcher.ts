// The TwinStore desktop launcher (launcher/ in the repo) serves the app at its own address and
// answers /__twinstore/*. Under the Vite dev server those paths fall through to index.html, so the
// reply's shape is what tells the two apart.

import { useQuery } from "@tanstack/react-query";

async function detectLauncher(): Promise<boolean> {
  try {
    const r = await fetch("/__twinstore/ping", { cache: "no-store" });
    if (!r.ok || !r.headers.get("content-type")?.includes("application/json")) return false;
    const body = (await r.json()) as { app?: string };
    return body.app === "twinstore-launcher";
  } catch {
    return false;
  }
}

export function useLauncher(): boolean {
  const { data } = useQuery({ queryKey: ["launcher"], queryFn: detectLauncher, staleTime: Infinity, retry: false });
  return data ?? false;
}

export interface StoppedNote {
  title: string;
  body: string;
}

const STOPPED: StoppedNote = {
  title: "TwinStore stopped",
  body: "You can close this tab. Click the TwinStore icon to start it again.",
};

/** Stops the launcher and the server behind it, then leaves a note in place of the app. */
export async function quitLauncher(note: StoppedNote = STOPPED): Promise<void> {
  try {
    await fetch("/__twinstore/quit", { method: "POST", headers: { "X-TwinStore": "1" } });
  } catch {
    // already gone
  }
  const screen = document.createElement("div");
  screen.setAttribute("role", "status");
  screen.dataset.twinstoreStopped = "";
  screen.className =
    "fixed inset-0 z-[100] grid place-items-center bg-background/95 p-6 text-center backdrop-blur-xl";
  const box = document.createElement("div");
  box.className = "max-w-md space-y-2";
  const title = document.createElement("div");
  title.className = "font-display text-4xl";
  title.textContent = note.title;
  const body = document.createElement("p");
  body.className = "text-muted-foreground";
  body.textContent = note.body;
  box.append(title, body);
  screen.append(box);
  document.body.append(screen);
}
