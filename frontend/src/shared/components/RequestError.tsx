import { ApiError } from "@/shared/api/errors";
import { useI18n } from "@/shared/i18n/i18n";
import { UserMessageError } from "@/shared/i18n/userMessage";

export function RequestError({ error, children }: { error: unknown; children?: React.ReactNode }) {
  const { t } = useI18n();
  if (!error) return null;
  const status = error instanceof ApiError ? error.status : null;
  const key = status === 409 ? "requestConflict" : status === 404 ? "requestMissing"
    : status === 413 ? "requestLarge" : status === 400 || status === 422 ? "requestInvalid" : "requestFailed";
  return <div role="alert" className="space-y-1 break-words">
    <p>{error instanceof UserMessageError ? t(error.key, error.values) : t(key)}</p>
    {!(error instanceof UserMessageError) && error instanceof Error && error.message &&
      <details><summary>{t("requestDetails")}</summary><p className="whitespace-pre-wrap">{error.message}</p></details>}
    {children}
  </div>;
}
