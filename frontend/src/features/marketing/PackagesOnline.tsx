// Put a tested package online: a concept test's package image that is linked to a store product can replace that
// product's picture in a variant of an online store, so vision shoppers meet it on the web shop too.

import { useState } from "react";

import type { SurveyReport } from "@/shared/api/marketing";
import { useI18n } from "@/shared/i18n/i18n";

import { usePackages } from "./hooks";
import { TestOnline } from "./TestOnline";

export function PackagesOnline({ projectId, report: r }: { projectId: string; report: SurveyReport }) {
  const { t } = useI18n();
  const packages = usePackages(projectId);
  const linked = r.stimuli.flatMap((asset, i) => {
    const sku = packages.data?.find((p) => p.asset_id === asset)?.sku;
    return sku ? [{ asset, sku, name: r.stimulus_names[i] || asset }] : [];
  });
  const [picked, setPicked] = useState("");
  const chosen = linked.find((x) => x.asset === picked) ?? linked[0];
  if (!chosen) return null;
  return (
    <section className="rounded-2xl border bg-card p-4">
      {linked.length > 1 && (
        <select value={chosen.asset} onChange={(e) => setPicked(e.target.value)} aria-label={t("mkPackagePick")}
          className="h-8 max-w-full rounded-lg border bg-card px-2 text-xs">
          {linked.map((x) => <option key={x.asset} value={x.asset}>{x.name}</option>)}
        </select>
      )}
      <TestOnline key={chosen.asset} projectId={projectId} testName={r.name} currency={r.currency}
        variant={{ name: t("mkPackageVariant", { name: chosen.name }), changes: [{ kind: "package", sku: chosen.sku, asset_id: chosen.asset }] }} />
    </section>
  );
}
