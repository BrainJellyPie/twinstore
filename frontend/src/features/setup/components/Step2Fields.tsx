import { useRef, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";
import { Textarea } from "@/shared/components/ui/textarea";

import { SupplementalUpload } from "./SupplementalUpload";
import type { Step2Errors, WizardValues } from "../validate";

interface Step2FieldsProps {
  values: WizardValues;
  errors: Step2Errors | undefined;
  disabled?: boolean;
  onChange: <K extends keyof WizardValues>(key: K, value: WizardValues[K]) => void;
}

const DAYS: Record<WizardValues["workingDayPreset"], string> = { "7": "every day", weekday: "Monday to Friday", weekend: "weekends" };

export function Step2Fields({ values, errors, disabled, onChange }: Step2FieldsProps) {
  const { t, locale } = useI18n();
  // Plain state rather than a query mutation: the wizard also renders outside the app's query provider.
  const [drafting, setDrafting] = useState(false);
  const [drafted, setDrafted] = useState<string | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const request = useRef(0);
  const draft = async () => {
    const id = ++request.current;
    setDrafting(true);
    setDraftError(null);
    try {
      const r = await api.draftCustomerProfile({
        name: values.name, description: values.description, address: values.address, store_type: values.storeType,
        hours: `${values.openHour}:00–${values.closeHour}:00, ${DAYS[values.workingDayPreset]}`, locale,
      });
      if (id !== request.current) return;
      setDrafted(r.profile);
      onChange("customerProfile", r.profile);
    } catch (e) {
      if (id === request.current) setDraftError(e instanceof Error ? e.message : String(e));
    } finally {
      if (id === request.current) setDrafting(false);
    }
  };
  return (
    <div className="space-y-6">
      <div className="rounded-md bg-muted p-3 text-sm">
        {t("customerProfileHint")}
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium" htmlFor="setup-customer-profile">{t("customerProfile")}</label>
        <Textarea
          id="setup-customer-profile"
          value={values.customerProfile}
          disabled={disabled}
          rows={3}
          placeholder={t("customerProfilePlaceholder")}
          onChange={(e) => onChange("customerProfile", e.target.value)}
          aria-required="true"
          aria-describedby={errors?.customerProfile ? "setup-customer-profile-error" : undefined}
          aria-invalid={errors?.customerProfile ? true : undefined}
        />
        {errors?.customerProfile && (
          <p id="setup-customer-profile-error" role="alert" className="text-xs text-destructive">{errors.customerProfile}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => void draft()} disabled={disabled || drafting}
            className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50">
            {drafting ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5 text-primary" />}
            {drafting ? t("draftingCustomerProfile") : t("draftCustomerProfile")}
          </button>
          {drafted !== null && values.customerProfile === drafted && (
            <span className="text-xs text-muted-foreground">{t("draftedCustomerProfileHint")}</span>
          )}
          {draftError && <span role="alert" className="text-xs text-destructive">{draftError}</span>}
        </div>
      </div>

      <SupplementalUpload
        file={values.supplementalFile}
        onFileChange={(f) => onChange("supplementalFile", f)}
        error={errors?.supplementalFile}
        disabled={disabled}
      />
    </div>
  );
}
