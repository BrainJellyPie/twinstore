// Grid-editor API client.
//
// Design notes:
// - shared/api/client.ts's fetchJson throws Error on non-2xx. Here we want to preserve
//   the 4-field (code/reason/message/details) error structure so React components can
//   branch on it directly — hence the discriminated-union return pattern.
// - Both loadSetup (GET) and saveSetup (PUT) return `{ok: true, ...} | {ok: false, ...}`.
// - When the body is not JSON (e.g. dev-proxy 502 plaintext) it's normalized to
//   `code: "non_json_response"`, `reason: "transport_error"`.

import { BASE } from "@/shared/api/client";
import { apiFetch } from "@/shared/api/errors";
import type {
  SaveSetupResult,
  SetupUpdatePayload,
  SetupDetailWithBlocked,
  LoadSetupResult,
  SetupSummary,
  ClearedSlotInfo,
  BlockedFaceDetail,
  Issue,
} from "./types";

// Extracts the 4 fields from FastAPI's `{detail: {code, reason, message, details}}`.
// Falls back safely when detail is a plain string or a non-standard shape.
interface FastApiErrorBody {
  detail?:
    | {
        code?: unknown;
        reason?: unknown;
        message?: unknown;
        details?: unknown;
      }
    | string
    | unknown;
}

function normalizeErrorBody(
  status: number,
  body: FastApiErrorBody | unknown,
): { code: string; reason: string; message: string; details: Record<string, unknown> } {
  const detail = (body as FastApiErrorBody)?.detail;
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    return {
      code: typeof d.code === "string" ? d.code : `http_${status}`,
      reason: typeof d.reason === "string" ? d.reason : "unknown",
      message: typeof d.message === "string" ? d.message : `HTTP ${status}`,
      details:
        d.details && typeof d.details === "object"
          ? (d.details as Record<string, unknown>)
          : {},
    };
  }
  if (typeof detail === "string") {
    return {
      code: `http_${status}`,
      reason: "unknown",
      message: detail,
      details: {},
    };
  }
  return {
    code: `http_${status}`,
    reason: "unknown",
    message: `HTTP ${status}`,
    details: {},
  };
}

// Safely reads a JSON body from a fetch response. On parse failure, returns the raw
// text with a `non_json_response` signal so callers can surface a transport error.
async function readJsonOrText(
  res: Response,
): Promise<{ kind: "json"; body: unknown } | { kind: "text"; body: string }> {
  const text = await res.text();
  if (text.length === 0) {
    return { kind: "json", body: {} };
  }
  try {
    return { kind: "json", body: JSON.parse(text) };
  } catch {
    return { kind: "text", body: text };
  }
}

export async function loadSetup(
  pid: string,
  sid: string,
  signal?: AbortSignal,
): Promise<LoadSetupResult> {
  const res = await apiFetch(`${BASE}/api/projects/${pid}/setups/${sid}`, {
    method: "GET",
    signal,
  });
  const parsed = await readJsonOrText(res);

  if (!res.ok) {
    if (parsed.kind === "json") {
      const err = normalizeErrorBody(res.status, parsed.body);
      return { ok: false, status: res.status, ...err };
    }
    return {
      ok: false,
      status: res.status,
      code: "non_json_response",
      reason: "transport_error",
      message: parsed.body,
      details: {},
    };
  }

  if (parsed.kind !== "json") {
    return {
      ok: false,
      status: res.status,
      code: "non_json_response",
      reason: "transport_error",
      message: parsed.body,
      details: {},
    };
  }
  // Legacy responses may omit `blocked_faces` — coerce to an empty array.
  const detail = parsed.body as Omit<SetupDetailWithBlocked, "blocked_faces"> & {
    blocked_faces?: BlockedFaceDetail[];
  };
  return {
    ok: true,
    detail: { ...detail, blocked_faces: detail.blocked_faces ?? [] },
  };
}

export async function saveSetup(
  pid: string,
  sid: string,
  payload: SetupUpdatePayload,
  signal?: AbortSignal,
): Promise<SaveSetupResult> {
  const res = await apiFetch(`${BASE}/api/projects/${pid}/setups/${sid}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ setup: payload }),
    signal,
  });
  const parsed = await readJsonOrText(res);

  if (!res.ok) {
    if (parsed.kind === "json") {
      const err = normalizeErrorBody(res.status, parsed.body);
      return { ok: false, status: res.status, ...err };
    }
    return {
      ok: false,
      status: res.status,
      code: "non_json_response",
      reason: "transport_error",
      message: parsed.body,
      details: {},
    };
  }

  if (parsed.kind !== "json") {
    return {
      ok: false,
      status: res.status,
      code: "non_json_response",
      reason: "transport_error",
      message: parsed.body,
      details: {},
    };
  }
  const body = parsed.body as {
    setup: SetupSummary;
    cleared: ClearedSlotInfo[];
    blocked_faces: BlockedFaceDetail[];
    issues: Issue[];
  };
  return {
    ok: true,
    setup: body.setup,
    cleared: body.cleared,
    blocked_faces: body.blocked_faces,
    issues: body.issues,
  };
}
