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

export function Step2Fields({ values, errors, disabled, onChange }: Step2FieldsProps) {
  const { t } = useI18n();
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
