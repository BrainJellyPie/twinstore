import { useCallback, useState } from "react";

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
  type Step1Errors,
  type Step2Errors,
  type WizardValues,
} from "../validate";
import { Step1Fields } from "./Step1Fields";
import { Step2Fields } from "./Step2Fields";
import { WizardHeader } from "./WizardHeader";

interface CreateStoreWizardProps {
  onCreated?: (projectId: string) => void;
}

const STEPS = [
  { index: 1, label: "The store", hint: "Name, address and opening hours. The address grounds the trade-area analysis." },
  { index: 2, label: "Its shoppers", hint: "Synthetic personas for every open hour, generated from the neighborhood's demographics." },
] as const;

export function CreateStoreWizard({ onCreated }: CreateStoreWizardProps = {}) {
  const [step, setStep] = useState<1 | 2>(1);
  const [values, setValues] = useState<WizardValues>({ ...DEFAULT_VALUES, storeType: "convenience" });
  const [withTemplate, setWithTemplate] = useState(true);
  const [template, setTemplate] = useState(DEFAULT_TEMPLATE_CHOICE);
  const layoutValid = !withTemplate || validTemplateChoice(template);
  const [step1Errors, setStep1Errors] = useState<Step1Errors | null>(null);
  const [step2Errors, setStep2Errors] = useState<Step2Errors | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const create = useCreateStore();

  const onChange = useCallback(
    <K extends keyof WizardValues>(key: K, value: WizardValues[K]) => {
      setValues((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const handleNext = useCallback(() => {
    if (!layoutValid) return;
    const r = validateStep1(values);
    if (!r.ok) {
      setStep1Errors(r.errors);
      return;
    }
    setStep1Errors(null);
    setStep(2);
  }, [values, layoutValid]);

  const handleSubmitClick = useCallback(() => {
    const r1 = validateStep1(values);
    const r2 = validateStep2(values);
    if (!r1.ok) setStep1Errors(r1.errors);
    if (!r2.ok) setStep2Errors(r2.errors);
    if (!r1.ok || !r2.ok || !layoutValid) return;
    setStep1Errors(null);
    setStep2Errors(null);
    setConfirmOpen(true);
  }, [values, layoutValid]);

  const handleConfirmedSubmit = useCallback(async () => {
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
      onCreated?.(res.metadata.project_id);
    } catch {
      // create.error → rendered below
    }
  }, [values, create, onCreated, withTemplate, template]);

  const step1Ok = validateStep1(values).ok && layoutValid;
  const step2Ok = validateStep2(values).ok;
  const errMessage = create.error instanceof Error
    ? create.error.message
    : null;
  const isPending = create.isPending;

  return (
    <div className="relative flex-1 overflow-y-auto">
      <div className="hero-glow pointer-events-none absolute inset-x-0 top-0 h-[32rem] [mask-image:linear-gradient(to_bottom,black,transparent)]" aria-hidden />
      <div className="relative mx-auto grid w-full max-w-6xl gap-10 px-6 py-10 lg:grid-cols-[22rem_1fr] lg:py-14">
        <aside className="lg:sticky lg:top-10 lg:self-start">
          <WizardHeader title="New store" steps={STEPS} activeIndex={step} />
        </aside>
        <div className="panel animate-rise space-y-8 rounded-[2rem] p-8 sm:p-10">

        {step === 1 && (
          <>
            <Step1Fields values={values} errors={step1Errors ?? undefined} disabled={isPending} onChange={onChange} />
            <fieldset className="space-y-3 rounded-xl border p-4" disabled={isPending}>
              <legend className="px-1 text-sm font-medium">Starting layout</legend>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={withTemplate} onChange={(e) => setWithTemplate(e.target.checked)} />
                Start with a furnished store template
              </label>
              {withTemplate ? <TemplatePicker value={template} onChange={setTemplate}
                onTemplateSelected={(format) => onChange("storeType", format.store_type)} />
                : <p className="text-xs text-muted-foreground">Start with an empty layout to draw or import your own floor plan.</p>}
              <p className="text-xs text-muted-foreground">Your store name, type and opening hours above apply to the initial layout. More layouts and multi-floor stores can be added from the project.</p>
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
          <p className="text-sm text-destructive">{errMessage}</p>
        )}

        <div className="flex items-center justify-between">
          {step === 2 ? (
            <Button type="button" size="lg" variant="outline" className="h-10 rounded-xl px-5 text-base" disabled={isPending} onClick={() => setStep(1)}>
              Back
            </Button>
          ) : (
            <span />
          )}
          {step === 1 ? (
            <Button type="button" size="lg" className="h-10 rounded-xl px-6 text-base" disabled={!step1Ok} onClick={handleNext}>
              Next
            </Button>
          ) : (
            <Button type="button" size="lg" className="h-10 rounded-xl px-6 text-base" disabled={!step1Ok || !step2Ok || isPending} onClick={handleSubmitClick}>
              {isPending ? "Creating store…" : "Create new store"}
            </Button>
          )}
        </div>
        </div>
      </div>
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent className="data-[size=default]:sm:max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle>Generate personas?</AlertDialogTitle>
            <AlertDialogDescription>
              This will consume API tokens based on your daily visitor cap. Continue?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmedSubmit}>Generate</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
