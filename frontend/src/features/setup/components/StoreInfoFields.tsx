import { useI18n } from "@/shared/i18n/i18n";
import { isStoreTypeId, storeTypeLabel } from "@/shared/i18n/storeLabels";
import { cn } from "@/shared/utils/cn";
import { Input } from "@/shared/components/ui/input";
import { Textarea } from "@/shared/components/ui/textarea";

import type { Step1Errors } from "../validate";

const labelClass = "text-sm font-medium";
const errorTextClass = "text-xs text-destructive";
const errorBorderClass = "border-destructive focus-visible:border-destructive";

export interface StoreInfoFieldsProps {
  name: string;
  description: string;
  address: string;
  storeType: string;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onAddressChange: (value: string) => void;
  onStoreTypeChange: (value: string) => void;
  errors?: Pick<Step1Errors, "name" | "address" | "storeType">;
  disabled?: boolean;
}

export function StoreInfoFields({
  name,
  description,
  address,
  storeType,
  onNameChange,
  onDescriptionChange,
  onAddressChange,
  onStoreTypeChange,
  errors,
  disabled,
}: StoreInfoFieldsProps) {
  const { t, locale } = useI18n();
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <label className={labelClass} htmlFor="setup-store-name">
          {t("storeName")}
        </label>
        <Input
          id="setup-store-name"
          className={cn(errors?.name && errorBorderClass)}
          value={name}
          maxLength={200}
          placeholder={t("storeNamePlaceholder")}
          disabled={disabled}
          aria-required="true"
          aria-describedby={errors?.name ? "setup-store-name-error" : undefined}
          aria-invalid={errors?.name ? true : undefined}
          onChange={(e) => onNameChange(e.target.value)}
        />
        {errors?.name && <p id="setup-store-name-error" role="alert" className={errorTextClass}>{errors.name}</p>}
      </div>

      <div className="space-y-1.5">
        <label className={labelClass} htmlFor="setup-store-description">
          {t("descriptionOptional")}
        </label>
        <Textarea
          id="setup-store-description"
          value={description}
          rows={3}
          disabled={disabled}
          onChange={(e) => onDescriptionChange(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <label className={labelClass} htmlFor="setup-store-address">
          {t("address")}
        </label>
        <Input
          id="setup-store-address"
          className={cn(errors?.address && errorBorderClass)}
          value={address}
          placeholder={t("addressPlaceholder")}
          disabled={disabled}
          aria-required="true"
          aria-describedby={errors?.address ? "setup-store-address-error" : undefined}
          aria-invalid={errors?.address ? true : undefined}
          onChange={(e) => onAddressChange(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          {t("addressHint")}
        </p>
        {errors?.address && <p id="setup-store-address-error" role="alert" className={errorTextClass}>{errors.address}</p>}
      </div>

      <div className="space-y-1.5">
        <label className={labelClass} htmlFor="setup-store-type">
          {t("storeType")}
        </label>
        <Input
          id="setup-store-type"
          className={cn(errors?.storeType && errorBorderClass)}
          // A category id from the defaults or a template ("convenience") reads as its label; typing replaces it.
          value={isStoreTypeId(storeType) ? storeTypeLabel(storeType, locale) : storeType}
          placeholder={t("storeTypePlaceholder")}
          disabled={disabled}
          aria-required="true"
          aria-describedby={errors?.storeType ? "setup-store-type-error" : undefined}
          aria-invalid={errors?.storeType ? true : undefined}
          onChange={(e) => onStoreTypeChange(e.target.value)}
        />
        {errors?.storeType && <p id="setup-store-type-error" role="alert" className={errorTextClass}>{errors.storeType}</p>}
      </div>
    </div>
  );
}
