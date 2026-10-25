import { createRouter } from "@tanstack/react-router";
import { routeTree } from "@/routeTree.gen";
import { NotFound, RouteError } from "@/app/RouteError";

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  defaultPreloadStaleTime: 0,
  defaultErrorComponent: RouteError,
  defaultNotFoundComponent: NotFound,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
