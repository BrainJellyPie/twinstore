import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { StoreSetupDraft } from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";
import { TemplatePicker } from "@/features/layouts/components/TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE, templateRequest, validTemplateChoice } from "@/features/layouts/templateOptions";
import { Button } from "@/shared/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
import { useCreateStore } from "@/shared/mutations/useCreateStore";

import {
  DEFAULT_VALUES,
  buildWeeklySchedule,
  validateStep1,
  validateStep2,
  type WizardValues,
} from "../validate";
import { DescribeStoreField } from "./DescribeStoreField";
import { Step1Fields } from "./Step1Fields";
import { Step2Fields } from "./Step2Fields";
import { WizardHeader } from "./WizardHeader";

interface CreateStoreWizardProps {
  onCreated?: (projectId: string) => void;
}

const STEPS = [
  { index: 1, label: "wizardStore", hint: "wizardStoreHint" },
  { index: 2, label: "wizardShoppers", hint: "wizardShoppersHint" },
] as const;

export function CreateStoreWizard({ onCreated }: CreateStoreWizardProps = {}) {
  const { locale, t } = useI18n();
  const steps = STEPS.map((item) => ({ ...item, label: t(item.label), hint: t(item.hint) }));
  const [step, setStep] = useState<1 | 2>(1);
  const [values, setValues] = useState<WizardValues>({ ...DEFAULT_VALUES, storeType: "convenience" });
  const [withTemplate, setWithTemplate] = useState(true);
  const [templateOptions, setTemplate] = useState(DEFAULT_TEMPLATE_CHOICE);
  const template = useMemo(() => ({ ...templateOptions, weekly_hours: null, open_hour: values.openHour, close_hour: values.closeHour,
    closed_days: buildWeeklySchedule(values).filter((day) => !day.is_open).map((day) => day.day) }), [templateOptions, values]);
  const layoutValid = !withTemplate || validTemplateChoice(template);
  const [showStep1Errors, setShowStep1Errors] = useState(false);
  const [showStep2Errors, setShowStep2Errors] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const create = useCreateStore();
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const previousStep = useRef(step);
  useEffect(() => {
    if (previousStep.current === step) return;
    previousStep.current = step;
    document.getElementById(step === 1 ? "setup-store-name" : "setup-customer-profile")?.focus();
  }, [step]);
  const result1 = validateStep1(values, locale);
  const result2 = validateStep2(values, locale);
  const step1Errors = showStep1Errors && !result1.ok ? result1.errors : undefined;
  const step2Errors = showStep2Errors && !result2.ok ? result2.errors : undefined;
  // Missing details and invalid hours are explained on Next; invalid geometry stays blocked.
  const geometryValid = !withTemplate || validTemplateChoice({ ...template, open_hour: 0, close_hour: 24, closed_days: [] });

  const onChange = useCallback(
    <K extends keyof WizardValues>(key: K, value: WizardValues[K]) => {
      setValues((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  // One description fills the form: only the fields it speaks to, and the starting format when one fits.
  const fillFromDescription = useCallback((d: StoreSetupDraft) => {
    setValues((prev) => ({
      ...prev,
      ...(d.name ? { name: d.name } : {}),
      ...(d.description ? { description: d.description } : {}),
      ...(d.address ? { address: d.address } : {}),
      ...(d.store_type ? { storeType: d.store_type } : {}),
      ...(d.open_days ? { workingDayPreset: d.open_days } : {}),
      ...(d.open_hour != null && d.close_hour != null ? { openHour: d.open_hour, closeHour: d.close_hour } : {}),
    }));
    if (d.template_id) {
      setWithTemplate(true);
    }
    if (d.template_id || d.currency) setTemplate((prev) => ({ ...prev,
      ...(d.template_id ? { templateId: d.template_id } : {}), ...(d.currency ? { currency: d.currency } : {}),
    }));
  }, []);

  const handleNext = useCallback(() => {
    if (create.isPending) return;
    const result = validateStep1(values, locale);
    if (!result.ok) {
      setShowStep1Errors(true);
      const field = result.errors.name ? "setup-store-name" : result.errors.address ? "setup-store-address"
        : result.errors.storeType ? "setup-store-type" : result.errors.openHour ? "setup-open-hour" : "setup-close-hour";
      document.getElementById(field)?.focus();
      return;
    }
    if (!layoutValid) return;
    setShowStep1Errors(false);
    setStep(2);
  }, [values, layoutValid, locale, create.isPending]);

  const handleSubmitClick = useCallback(() => {
    if (create.isPending) return;
    const result1 = validateStep1(values, locale);
    const result2 = validateStep2(values, locale);
    if (!result1.ok || !layoutValid) {
      setShowStep1Errors(true);
      setStep(1);
      return;
    }
    if (!result2.ok) {
      setShowStep2Errors(true);
      document.getElementById(result2.errors.customerProfile ? "setup-customer-profile" : "setup-supplemental-remove")?.focus();
      return;
    }
    setShowStep1Errors(false);
    setShowStep2Errors(false);
    setConfirmOpen(true);
  }, [values, layoutValid, locale, create.isPending]);

  const handleConfirmedSubmit = useCallback(async () => {
    if (create.isPending) return;
    setConfirmOpen(false);
    try {
      const res = await create.mutateAsync({
        meta: {
          name: values.name.trim(),
          description: values.description,
          address: values.address.trim(),
          store_type: values.storeType.trim(),
          customer_profile: values.customerProfile.trim(),
          weekly_schedule: buildWeeklySchedule(values),
          layout: withTemplate ? templateRequest(template) : null,
        },
        supplemental: values.supplementalFile,
      });
      if (mounted.current) onCreated?.(res.metadata.project_id);
    } catch {
      // create.error → rendered below
    }
  }, [values, create, onCreated, withTemplate, template]);

  const errMessage = create.error instanceof Error
    ? create.error.message
    : null;
  const isPending = create.isPending;

  return (
    <div className="relative flex-1 overflow-y-auto">
      <div className="hero-glow pointer-events-none absolute inset-x-0 top-0 h-[32rem] [mask-image:linear-gradient(to_bottom,black,transparent)]" aria-hidden />
      <div className="relative mx-auto grid w-full min-w-0 max-w-6xl grid-cols-1 gap-10 px-6 py-10 lg:grid-cols-[22rem_1fr] lg:py-14">
        <aside className="min-w-0 lg:sticky lg:top-10 lg:self-start">
          <WizardHeader title={t("newStore")} steps={steps} activeIndex={step} />
        </aside>
        <div className="panel min-w-0 animate-rise space-y-8 rounded-[2rem] p-5 sm:p-10">

        {step === 1 && (
          <>
            <DescribeStoreField disabled={isPending} onFilled={fillFromDescription}
              formKey={JSON.stringify([values, withTemplate, templateOptions])} />
            <Step1Fields values={values} errors={step1Errors ?? undefined} disabled={isPending} onChange={onChange} />
            <fieldset className="space-y-3 rounded-xl border p-4" disabled={isPending}>
              <legend className="px-1 text-sm font-medium">{t("startingLayout")}</legend>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={withTemplate} onChange={(e) => setWithTemplate(e.target.checked)} />
                {t("furnishedTemplate")}
              </label>
              {withTemplate ? <TemplatePicker value={template} onChange={setTemplate} showOperatingHours={false} defaultCustomizationOpen={false}
                onTemplateSelected={(format) => onChange("storeType", format.store_type)} />
                : <p className="text-xs text-muted-foreground">{t("emptyLayoutHint")}</p>}
              <p className="text-xs text-muted-foreground">{t("initialLayoutHint")}</p>
            </fieldset>
          </>
        )}
        {step === 2 && (
          <Step2Fields
            values={values}
            errors={step2Errors ?? undefined}
            disabled={isPending}
            onChange={onChange}
          />
        )}

        {errMessage && step === 2 && (
          <p role="alert" className="text-sm text-destructive">{errMessage}</p>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {step === 2 ? (
            <Button type="button" size="lg" variant="outline" className="h-10 w-full rounded-xl px-5 text-base sm:w-auto" disabled={isPending} onClick={() => setStep(1)}>
              {t("back")}
            </Button>
          ) : (
            <span className="hidden sm:block" />
          )}
          {step === 1 ? (
            <Button type="button" size="lg" className="h-10 w-full rounded-xl px-6 text-base sm:w-auto" disabled={!geometryValid || isPending} onClick={handleNext}>
              {t("next")}
            </Button>
          ) : (
            <Button type="button" size="lg" className="h-10 w-full rounded-xl px-6 text-base sm:w-auto" disabled={isPending} onClick={handleSubmitClick}>
              {isPending ? t("creatingStore") : t("createNewStore")}
            </Button>
          )}
        </div>
        </div>
      </div>
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent className="max-h-[92vh] overflow-y-auto data-[size=default]:sm:max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle>{t("generatePersonas")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("generatePersonasHint")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <dl className="min-w-0 space-y-2 text-sm">
            <div><dt className="text-xs text-muted-foreground">{t("storeName")}</dt><dd className="break-words">{values.name.trim()}</dd></div>
            <div><dt className="text-xs text-muted-foreground">{t("address")}</dt><dd className="break-words">{values.address.trim()}</dd></div>
            <div><dt className="text-xs text-muted-foreground">{t("customerProfile")}</dt><dd className="break-words whitespace-pre-wrap">{values.customerProfile.trim()}</dd></div>
            {values.supplementalFile && <div><dt className="text-xs text-muted-foreground">{t("supplementalData")}</dt><dd className="break-all">{values.supplementalFile.name}</dd></div>}
          </dl>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction disabled={isPending} onClick={handleConfirmedSubmit}>{t("generate")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
