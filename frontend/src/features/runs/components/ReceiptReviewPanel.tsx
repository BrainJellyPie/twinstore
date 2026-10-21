import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/shared/components/ui/button";
import { reviewReceipts, type ReceiptLine, type ReceiptReading, type ReceiptsResult } from "@/shared/api/client";

interface Props {
  projectId: string;
  runId: string;
  result: ReceiptsResult;
  scoring: boolean;
  onScore: (file: File) => void;
}

const inputClass = "min-w-0 w-full rounded border bg-background px-2 py-1 text-xs";

export function ReceiptReviewPanel({ projectId, runId, result, scoring, onScore }: Props) {
  const [drafts, setDrafts] = useState(() => result.receipts.map((receipt) => ({
    receipt, included: true, excluded: [] as number[],
  })));
  const review = useMutation({ mutationFn: (receipts: ReceiptReading[]) => reviewReceipts(projectId, runId, receipts) });
  const busy = scoring || review.isPending;

  function editReceipt(index: number, change: Partial<ReceiptReading>) {
    review.reset();
    setDrafts((rows) => rows.map((row, i) => i === index ? { ...row, receipt: { ...row.receipt, ...change } } : row));
  }

  function editLine(receiptIndex: number, lineIndex: number, change: Partial<ReceiptLine>) {
    review.reset();
    setDrafts((rows) => rows.map((row, ri) => ri === receiptIndex ? {
      ...row, receipt: { ...row.receipt, lines: row.receipt.lines.map((line, li) => li === lineIndex ? { ...line, ...change } : line) },
    } : row));
  }

  function check() {
    review.mutate(drafts.filter((d) => d.included).map((d) => ({ ...d.receipt, lines: d.receipt.lines.filter((_, i) => !d.excluded.includes(i)) })));
  }

  return (
    <section aria-label="Review receipt readings" className="my-3 space-y-3 rounded border p-3">
      <div>
        <h4 className="text-sm font-medium">Review receipts before scoring</h4>
        <p className="text-xs text-muted-foreground">
          Confirm product matches, quantities and amounts. Prices use {result.currency} minor units
          (for example, USD 2.49 = 249; KRW 2,500 = 2500). Line totals include discounts.
          Excluded lines change basket comparisons. Exclude duplicate photos and receipts from other stores.
        </p>
      </div>
      <fieldset disabled={busy} className="space-y-3">
        {drafts.map(({ receipt, included, excluded }, ri) => (
          <div key={ri} className="space-y-2 rounded border p-2">
            <label className="flex items-center gap-2 text-xs font-medium">
              <input type="checkbox" checked={included} onChange={(e) => {
                review.reset();
                setDrafts((rows) => rows.map((d, i) => i === ri ? { ...d, included: e.target.checked } : d));
              }} />
              Include {receipt.receipt_id} {receipt.store && `· ${receipt.store}`}
            </label>
            {receipt.notes.map((note, i) => <p key={i} className="text-xs text-muted-foreground">{note}</p>)}
            {included && <>
              <div className="grid grid-cols-2 gap-2">
                <label className="text-xs">Currency
                  <input aria-label={`Currency for ${receipt.receipt_id}`} className={inputClass} value={receipt.currency}
                    onChange={(e) => editReceipt(ri, { currency: e.target.value })} />
                </label>
                <label className="text-xs">Local date and time
                  <input aria-label={`Time for ${receipt.receipt_id}`} className={inputClass} value={receipt.timestamp}
                    placeholder="2026-10-21 14:05" onChange={(e) => editReceipt(ri, { timestamp: e.target.value })} />
                </label>
              </div>
              <label className="block text-xs">Printed receipt total (minor units)
                <input aria-label={`Total for ${receipt.receipt_id}`} type="number" min="0" step="1" className={inputClass} value={receipt.total ?? ""}
                  onChange={(e) => editReceipt(ri, { total: e.target.value === "" ? null : Number(e.target.value) })} />
              </label>
              {receipt.lines.length === 0 && <p className="text-xs text-destructive">No lines were read. Exclude this receipt and retry with a clearer photo.</p>}
              {receipt.lines.map((line, li) => {
                const label = `${receipt.receipt_id} line ${li + 1}`;
                return (
                  <div key={li} className="space-y-1 border-t pt-2">
                    <label className="flex gap-2 text-xs">
                      <input type="checkbox" aria-label={`Include ${label}`} checked={!excluded.includes(li)} onChange={(e) => {
                        review.reset();
                        setDrafts((rows) => rows.map((d, i) => i === ri ? { ...d, excluded: e.target.checked ? d.excluded.filter((k) => k !== li) : [...d.excluded, li] } : d));
                      }} />
                      {line.name || `Line ${li + 1}`}
                    </label>
                    {!excluded.includes(li) && <>
                      <select aria-label={`Product for ${label}`} className={inputClass} value={line.sku}
                        onChange={(e) => editLine(ri, li, { sku: e.target.value })}>
                        <option value="">Choose a product…</option>
                        {Object.entries(result.products).map(([sku, name]) => <option key={sku} value={sku}>{name} ({sku})</option>)}
                      </select>
                      <div className="grid grid-cols-3 gap-2">
                        <label className="text-xs">Quantity
                          <input aria-label={`Quantity for ${label}`} type="number" min="0" step="any" className={inputClass} value={line.quantity}
                            onChange={(e) => editLine(ri, li, { quantity: Number(e.target.value) })} />
                        </label>
                        <label className="text-xs">Unit price
                          <input aria-label={`Unit price for ${label}`} type="number" min="0" step="1" className={inputClass} value={line.unit_price ?? ""}
                            onChange={(e) => editLine(ri, li, { unit_price: e.target.value === "" ? null : Number(e.target.value) })} />
                        </label>
                        <label className="text-xs">Line total
                          <input aria-label={`Line total for ${label}`} type="number" min="0" step="1" className={inputClass} value={line.line_total ?? ""}
                            onChange={(e) => editLine(ri, li, { line_total: e.target.value === "" ? null : Number(e.target.value) })} />
                        </label>
                      </div>
                    </>}
                  </div>
                );
              })}
            </>}
          </div>
        ))}
      </fieldset>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={busy} onClick={check}>{review.isPending ? "Checking…" : "Check receipts"}</Button>
        <Button size="sm" disabled={busy || !review.data?.ready} onClick={() => {
          if (review.data?.ready) onScore(new File([review.data.csv], "reviewed-receipts.csv", { type: "text/csv" }));
        }}>Use reviewed receipts</Button>
      </div>
      {review.isError && <p role="alert" className="text-xs text-destructive">{review.error instanceof Error ? review.error.message : "Review failed"}</p>}
      {review.data && <div aria-live="polite" className="space-y-1 text-xs">
        <p>{review.data.ready ? `${review.data.included_lines} lines ready for validation.` : "Resolve the errors and check again."}</p>
        {review.data.issues.map((issue, i) => <p key={i} className={issue.severity === "error" ? "text-destructive" : "text-muted-foreground"}>
          {issue.receipt_id}{issue.line_index === null ? "" : ` · included line ${issue.line_index + 1}`}: {issue.message}
        </p>)}
      </div>}
    </section>
  );
}
