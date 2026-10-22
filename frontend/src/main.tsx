import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import "./index.css";
import "@/app/theme";
import { router } from "@/app/router";
import { QueryProvider } from "@/app/providers/QueryProvider";
import { reloadForNewVersion } from "@/app/staleBuild";

// A script of the previous version that is gone after an update: load the new version instead of failing.
window.addEventListener("vite:preloadError", (event) => {
  if (reloadForNewVersion()) event.preventDefault();
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryProvider>
      <RouterProvider router={router} />
    </QueryProvider>
  </StrictMode>,
);
