import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { factorialExport, factorialPreview } from "@/services/mutations/factorial";
import { factorialSourceQuery } from "@/services/queries/factorial";
import type { FactorialMetric } from "@/shared/api/factorial";
import { Button } from "@/shared/components/ui/button";

const format = (n: number | null) => n == null ? "Unavailable" : (n === 0 ? 0 : n).toLocaleString(undefined, { maximumSignificantDigits: 8 });

export function FactorialReview({ projectId, experimentId }: { projectId: string; experimentId: string }) {
  const [open, setOpen] = useState(false);
  const [price, setPrice] = useState(""); const [sign, setSign] = useState(""); const [both, setBoth] = useState("");
  const [metric, setMetric] = useState<FactorialMetric>("spend");
  const source = useQuery(factorialSourceQuery(projectId, experimentId, open));
  const preview = useMutation(factorialPreview(projectId, experimentId));
  const audit = useMutation(factorialExport(projectId, experimentId));
  const busy = source.isFetching || preview.isPending || audit.isPending;
  const clear = () => { preview.reset(); audit.reset(); };
  const report = preview.data?.request.source_sha256 === source.data?.source_sha256 ? preview.data : undefined;
  const valid = source.data?.available && !source.isError && source.data.price_arms.includes(price)
    && source.data.sign_arms.includes(sign) && source.data.combined_arms.includes(both) && new Set([price, sign, both]).size === 3;
  const error = source.error?.message || preview.error?.message || audit.error?.message;
  const exportCsv = () => {
    if (!report) return;
    audit.mutate(report.request, { onSuccess: (blob) => {
      const url = URL.createObjectURL(blob); const link = document.createElement("a");
      link.href = url; link.download = `${experimentId}-factorial.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
    } });
  };
  return <section aria-label="Price by sign factorial review" className="space-y-3 rounded-2xl border bg-card p-4 text-sm">
    <Button variant="outline" onClick={() => setOpen(!open)}>{open ? "Hide" : "Open"} price × sign analysis</Button>
    {open && <>
      <h3 className="font-semibold">Exploratory paired 2×2 analysis</h3>
      <p>Does the price effect change when a promotion sign is present? Select price-only, sign-only and combined variants from this experiment; Control supplies the fourth cell. No new simulation or model call.</p>
      <p className="text-xs text-muted-foreground">Each single-factor arm must contain one change on the same SKU. The combined arm must contain exactly those two changes. Additional manipulations, unapplied changes and identical effective layouts are rejected. For a new study, create these three variants in A/B tests before running it.</p>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => { clear(); void source.refetch(); }}>Reload paired source</Button>
      {source.isFetching && <p>Loading retained paired outcomes…</p>}
      {source.data && !source.data.available && <p>{source.data.reason}</p>}
      {source.data?.available && <>
        <div className="grid gap-3 sm:grid-cols-3">
          {([
            ["Price-only arm (10)", price, setPrice, source.data.price_arms],
            ["Sign-only arm (01)", sign, setSign, source.data.sign_arms],
            ["Combined arm (11)", both, setBoth, source.data.combined_arms],
          ] as const).map(([label, value, setter, options]) => <label key={label}>{label}<select aria-label={label} className="mt-1 block w-full rounded border bg-background p-2" disabled={busy} value={value} onChange={(e) => { clear(); setter(e.target.value); }}>
            <option value="">Choose an arm</option>{options.map((name) => <option key={name} value={name}>{name}</option>)}
          </select></label>)}
        </div>
        <label className="block">Outcome<select aria-label="Factorial outcome" className="ml-2 rounded border bg-background p-2" disabled={busy} value={metric} onChange={(e) => { clear(); setMetric(e.target.value as FactorialMetric); }}>
          <option value="spend">Whole-basket spend (minor units)</option><option value="units">Whole-basket units</option><option value="bought">Any purchase (0/1)</option>
        </select></label>
        <p className="text-xs">Selecting outcomes after seeing results is exploratory. The three-contrast adjustment does not cover trying other outcomes, arms or experiments. Synthetic shopper results do not establish real sales effects.</p>
        <Button disabled={!valid || busy} onClick={() => { clear(); if (source.data) preview.mutate({ source_sha256: source.data.source_sha256, price_arm: price, sign_arm: sign, combined_arm: both, metric }); }}>Calculate paired contrasts</Button>
      </>}
      {preview.isPending && <p>Calculating paired contrasts…</p>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
      {report && <div className="space-y-3">
        <p>{report.complete_panel} / {report.sampled_panel} sampled shoppers have all four cells ({report.requested_panel} requested). All displayed means use those same complete shoppers. Outcome: {report.request.metric}{report.request.metric === "spend" ? ` · ${report.currency} minor units` : ""}.</p>
        {!report.intervals_available && <p>Intervals withheld: require all sampled shoppers in all four cells and at least 30 complete shoppers. Missing outcomes are not zero.</p>}
        <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">Four-cell coverage and complete-cohort means</caption><thead><tr className="text-left"><th>Cell</th><th>Arm</th><th>Available</th><th>Mean</th></tr></thead><tbody>{report.cells.map((c) => <tr key={c.cell}><td>{c.cell}</td><td>{c.arm}</td><td>{c.available}</td><td>{format(c.mean)}</td></tr>)}</tbody></table></div>
        <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">Paired contrasts · approximate 95% family coverage for these three contrasts, under bootstrap assumptions</caption><thead><tr className="text-left"><th>Contrast</th><th>Estimate</th><th>Adjusted interval</th><th>Formula</th></tr></thead><tbody>{report.contrasts.map((c) => <tr key={c.name}><th className="py-2 text-left">{c.name}</th><td>{format(c.estimate)}</td><td>{c.ci_low == null || c.ci_high == null ? "Unavailable" : `[${format(c.ci_low)}, ${format(c.ci_high)}]`}</td><td>{c.formula}</td></tr>)}</tbody></table></div>
        <p className="break-all text-xs">Source SHA-256: {report.request.source_sha256}. Review selections are not saved; retain the audit export.</p>
        <Button variant="outline" disabled={busy || source.isError} onClick={exportCsv}>Export factorial audit CSV</Button>
        <details><summary className="cursor-pointer">Method and limitations</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
      </div>}
    </>}
  </section>;
}
