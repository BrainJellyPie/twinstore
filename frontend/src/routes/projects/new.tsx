import { createFileRoute, useNavigate, useRouter } from "@tanstack/react-router";

import { CreateStoreWizard } from "@/features/setup/components/CreateStoreWizard";

export const Route = createFileRoute("/projects/new")({
  component: NewProjectPage,
});

function NewProjectPage() {
  const navigate = useNavigate();
  const router = useRouter();
  return (
    <CreateStoreWizard
      onCreated={(pid) => {
        // Navigation can start before this page unmounts while the next route loads.
        if (router.state.location.pathname !== Route.fullPath) return;
        return navigate({ to: "/projects/$pid", params: { pid }, replace: true });
      }}
    />
  );
}
