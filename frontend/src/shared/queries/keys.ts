// Array-shaped keys so invalidateQueries can match by prefix
// (e.g. invalidating queryKeys.project(pid) invalidates everything under that project).
export const queryKeys = {
  projects: () => ["projects"] as const,
  project: (projectId: string) => ["projects", projectId] as const,
  setups: (projectId: string) => ["projects", projectId, "setups"] as const,
  setup: (projectId: string, setupId: string) =>
    ["projects", projectId, "setups", setupId] as const,
  runs: (projectId: string, setupId: string) =>
    ["projects", projectId, "setups", setupId, "runs"] as const,
  run: (projectId: string, runId: string) =>
    ["projects", projectId, "runs", runId] as const,
  runStatus: (projectId: string, runId: string) =>
    ["projects", projectId, "runs", runId, "status"] as const,
  // All runs of a project across layouts (compare dialog).
  projectRuns: (projectId: string) => ["projects", projectId, "all-runs"] as const,
  runDiagnostics: (projectId: string, runId: string) =>
    ["projects", projectId, "runs", runId, "diagnostics"] as const,
  compare: (projectId: string, runA: string, runB: string) =>
    ["projects", projectId, "compare", runA, runB] as const,
  engines: () => ["engines"] as const,
};
