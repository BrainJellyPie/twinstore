// The few provider and model names the server writes as English descriptions ("llama.cpp server", "Model loaded in
// llama-server"). Brand names stay as sent. A description is translated only while the server still sends the exact
// English text, so a renamed or user-made label is shown unchanged; kinds and model refs are never changed.

import type { MessageKey } from "./messages";

type Translate = (key: MessageKey, values?: Record<string, string | number>) => string;

const PROVIDERS: Record<string, [string, MessageKey]> = {
  vllm: ["vLLM (self-hosted)", "providerName_vllm"],
  llamacpp: ["llama.cpp server", "providerName_llamacpp"],
  custom: ["Other OpenAI-compatible", "providerName_custom"],
};
const SERVED = " (served name)";

export function providerLabel(kind: string, label: string, t: Translate): string {
  const known = Object.prototype.hasOwnProperty.call(PROVIDERS, kind) ? PROVIDERS[kind]! : null;
  return known && known[0] === label ? t(known[1]) : label;
}

/** `ref` is the model's `<provider kind>:<model id>` reference. */
export function modelLabel(ref: string, label: string, t: Translate): string {
  if (ref === "llamacpp:local" && label === "Model loaded in llama-server") return t("modelName_llamacppLocal");
  if (ref.startsWith("vllm:") && label.endsWith(SERVED)) return t("modelName_served", { name: label.slice(0, -SERVED.length) });
  return label;
}
