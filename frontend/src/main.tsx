import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import "./index.css";
import "@/app/theme";
import { router } from "@/app/router";
import { QueryProvider } from "@/app/providers/QueryProvider";
import { reloadForNewVersion } from "@/app/staleBuild";

// A script of the previous version that is gone after an update: load the new version instead of failing. The same
// error comes while the backend is stopped, so the router's own reload (which would land on the browser's "can't be
// reached" page) is marked as done; the error then reaches the page, which reloads only once the server answers.
window.addEventListener("vite:preloadError", (event) => {
  try {
    sessionStorage.setItem(`tanstack_router_reload:${event.payload.message}`, "1");
  } catch {
    // Without session storage the router reloads by itself, as before.
  }
  void reloadForNewVersion();
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryProvider>
      <RouterProvider router={router} />
    </QueryProvider>
  </StrictMode>,
);
