import { createRouter } from "@tanstack/react-router";
import { routeTree } from "@/routeTree.gen";
import { RouteError } from "@/app/RouteError";

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  defaultPreloadStaleTime: 0,
  defaultErrorComponent: RouteError,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
