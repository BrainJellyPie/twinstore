/** Read FastAPI's string and field-validation errors without exposing echoed input values. */
export function apiErrorMessage(body: string, fallback: string): string {
  let parsed: unknown;
  try { parsed = JSON.parse(body); } catch { return body.trim() || fallback; }
  if (typeof parsed === "string") return parsed.trim() || fallback;
  if (!parsed || typeof parsed !== "object" || !("detail" in parsed)) return fallback;
  const detail = parsed.detail;
  if (typeof detail === "string") return detail.trim() || fallback;
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
