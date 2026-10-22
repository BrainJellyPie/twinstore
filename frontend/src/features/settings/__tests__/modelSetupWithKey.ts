// Stand-in for useModelSetup in tests of screens that only mention the model setup: an API key is set, so nothing
// asks for a model and no query client is needed.
import type { ModelSetup } from "@/shared/api/client";

export const setupWithKey: ModelSetup = {
  warning: null, cloud_providers: ["OpenAI"],
  local: { state: "off", message: "", progress: null, downloaded_mb: 0, total_mb: 0, api_base: null, model_ref: "llamacpp:local",
    managed: false, runtime: "", downloaded: false },
  hardware: { os: "linux", arch: "x64", cpu: "CPU", cores: 4, threads: 8, ram_gb: 16, ram_free_gb: 8, gpus: [] },
  plan: { backend: "cpu", model: { key: "small", label: "Small model", repo: "model/repo", download_gb: 2, memory_gb: 2 },
    device: "CPU", gpu_layers: 0, threads: 4, parallel: 1, context: 4096, reason: "" },
};

const idle = { mutate: () => undefined, isPending: false, isError: false, error: null };

export const isPreparing = (setup: ModelSetup | undefined) =>
  !!setup && ["preparing", "downloading", "starting"].includes(setup.local.state);
export const modelAvailable = (setup: ModelSetup) =>
  setup.cloud_providers.length > 0 || setup.local.state === "ready" || isPreparing(setup);
export const useModelSetup = () => ({ data: setupWithKey });
export const useLocalModelControl = () => ({ start: idle, stop: idle });
