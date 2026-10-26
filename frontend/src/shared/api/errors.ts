/** A non-2xx API response; `status` lets callers react to a specific code such as 409. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Read FastAPI's string, structured ({code, message}) and field-validation errors without exposing echoed input values. */
export function apiErrorMessage(body: string, fallback: string): string {
  let parsed: unknown;
  try { parsed = JSON.parse(body); } catch { return body.trim() || fallback; }
  if (typeof parsed === "string") return parsed.trim() || fallback;
  if (!parsed || typeof parsed !== "object" || !("detail" in parsed)) return fallback;
  const detail = parsed.detail;
  if (typeof detail === "string") return detail.trim() || fallback;
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
    const message = detail.message.trim() || fallback;
    // A structured error can list what is wrong ({details: {issues: [{message}]}}, e.g. a layout's "no exit"):
    // say it, rather than only that something is.
    const listed = "details" in detail && detail.details && typeof detail.details === "object" && "issues" in detail.details
      && Array.isArray(detail.details.issues) ? detail.details.issues : [];
    const issues = listed.flatMap((issue: unknown) => issue && typeof issue === "object" && "message" in issue
      && typeof issue.message === "string" && issue.message.trim() ? [issue.message.trim()] : []);
    return issues.length ? `${message.replace(/[.:]$/, "")}: ${issues.join("; ")}.` : message;
  }
  if (!Array.isArray(detail)) return fallback;

  const messages: string[] = [];
  for (const issue of detail) {
    if (!issue || typeof issue !== "object" || !("msg" in issue) || typeof issue.msg !== "string" || !issue.msg.trim()) continue;
    const rawLocation = "loc" in issue && Array.isArray(issue.loc) ? issue.loc : [];
    const location = rawLocation.filter((part: unknown): part is string | number => typeof part === "string" || typeof part === "number");
    if (["body", "query", "path"].includes(String(location[0]))) location.shift();
    const field = location.join(".");
    messages.push(field ? `${field}: ${issue.msg}` : issue.msg);
  }
  return messages.join("; ") || fallback;
}
