import { expect, it } from "vitest";
import { translate } from "../i18n";
import { modelLabel, providerLabel } from "../providerLabels";

const ko = (key: Parameters<typeof translate>[1], values?: Record<string, string | number>) => translate("ko", key, values);

it("translates the server's descriptive provider and model names and keeps brand or changed names", () => {
  expect(providerLabel("llamacpp", "llama.cpp server", ko)).toBe("llama.cpp 서버");
  expect(providerLabel("custom", "Other OpenAI-compatible", ko)).toBe("기타 OpenAI 호환 서버");
  expect(providerLabel("openai", "OpenAI", ko)).toBe("OpenAI");
  expect(providerLabel("custom", "My gateway", ko)).toBe("My gateway");
  expect(modelLabel("llamacpp:local", "Model loaded in llama-server", ko)).toBe("llama-server에 불러온 모델");
  expect(modelLabel("vllm:Qwen/Qwen3.5-9B", "Qwen3.5-9B (served name)", ko)).toBe("Qwen3.5-9B (서버에 등록된 이름)");
  expect(modelLabel("llamacpp:my-model", "my-model", ko)).toBe("my-model");
  expect(modelLabel("openai:gpt-6-sol", "GPT-6 Sol", ko)).toBe("GPT-6 Sol");
});
