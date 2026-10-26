// Carry a tested variant to the online twin: its price, discount, category and package changes become a variant of
// an online store (matched by SKU), ready to run against that store on the same shoppers.

import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Globe2, Loader2 } from "lucide-react";

import type { Variant } from "@/shared/api/marketing";
import { listSites, onlineKeys, variantFromTest, type SiteSummary } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { focusOnMount } from "@/shared/utils/focusOnMount";

export function TestOnline({ projectId, testName, variant, currency }: {
  projectId: string; testName: string; variant: Variant; currency: string;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  // The products a store must sell for a change to reach it (a shelf sign has no web counterpart; a category matches by name).
  const skus = [...new Set(variant.changes.flatMap((c) => c.kind !== "promo" && c.kind !== "category_price" && c.sku ? [c.sku] : []))];
  const signOnly = variant.changes.every((c) => c.kind === "promo");
  const sites = useQuery({
    queryKey: [...onlineKeys.sites(projectId), "carrying", skus],
    queryFn: ({ signal }) => listSites(projectId, signal, skus),
    enabled: !signOnly,
  });
  // Stores that sell the most of the products first; one that sells none of them cannot take the changes.
  const usable = (sites.data ?? []).filter((s) => s.currency.toUpperCase() === currency.toUpperCase())
    .sort((a, b) => (b.carries ?? 0) - (a.carries ?? 0));
  // SKU counts cannot rule out a category-wide change; the server checks its category name.
  const hasCategoryChange = variant.changes.some((c) => c.kind === "category_price");
  const sells = (s: SiteSummary) => hasCategoryChange || !skus.length || s.carries == null || s.carries > 0;
  const [picked, setPicked] = useState("");
  const siteId = usable.some((s) => s.id === picked && sells(s)) ? picked : usable.find(sells)?.id ?? "";
  const store = usable.find((s) => s.id === siteId);
  const make = useMutation({
    mutationFn: () => variantFromTest(projectId, siteId, {
      name: `${store?.name ?? ""} – ${variant.name}`.slice(0, 60), note: `${testName}: ${variant.name}`.slice(0, 400),
      currency, changes: variant.changes,
    }),
    onSuccess: () => Promise.all([
      qc.invalidateQueries({ queryKey: onlineKeys.sites(projectId), exact: true }),
      qc.invalidateQueries({ queryKey: [...onlineKeys.sites(projectId), "carrying"] }),
    ]),
  });

  return (
    <div className="mt-3 space-y-2 rounded-xl border border-dashed border-primary/40 bg-primary/[0.03] p-3 text-xs">
      <div className="flex items-center gap-1.5 font-semibold text-foreground"><Globe2 className="size-3.5 text-primary" aria-hidden />{t("mkOnlineTitle")}</div>
      <p className="text-muted-foreground">{t("mkOnlineHint")}</p>
      {signOnly ? (
        <p className="text-muted-foreground">{t("mkOnlineSignOnly")}</p>
      ) : sites.isSuccess && !usable.some(sells) ? (
        <p className="text-muted-foreground">
          {t(usable.length ? "mkOnlineNoProducts" : "mkOnlineNone", { currency: currency.toUpperCase() })}{" "}
          <Link to="/online/$pid" params={{ pid: projectId }} className="text-primary underline-offset-2 hover:underline">{t("mkOnlineCreate")}</Link>
        </p>
      ) : make.data ? (
        // Replaces the button pressed, so focus moves here rather than dropping to the page.
        <div ref={focusOnMount} tabIndex={-1} className="space-y-1.5 rounded-md outline-offset-4">
          <p className="font-medium text-foreground">{t("mkOnlineMade", { name: make.data.site.name })}</p>
          <ul className="list-disc space-y-0.5 pl-4 text-muted-foreground">{make.data.applied.map((a) => <li key={a}>{a}</li>)}</ul>
          {make.data.skipped.length > 0 && (
            <div className="text-muted-foreground">
              <div className="font-medium">{t("mkOnlineSkipped")}</div>
              <ul className="list-disc space-y-0.5 pl-4">{make.data.skipped.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
          <Button asChild size="sm" className="gap-1.5">
            <Link to="/online/$pid" params={{ pid: projectId }} search={{ site: siteId, compare: make.data.site.id }}>
              {t("mkOnlineOpen")} <ArrowRight aria-hidden />
            </Link>
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <select value={siteId} onChange={(e) => setPicked(e.target.value)} disabled={!usable.length || make.isPending}
            aria-label={t("mkOnlinePick")} className="h-8 min-w-0 max-w-full flex-1 rounded-lg border bg-card px-2 text-xs">
            {usable.map((s) => <option key={s.id} value={s.id} disabled={!sells(s)}>{sells(s) ? s.name : t("mkOnlineNotSold", { name: s.name })}</option>)}
          </select>
          <Button size="sm" variant="outline" className="gap-1.5" onClick={() => make.mutate()} disabled={!siteId || make.isPending}>
            {make.isPending && <Loader2 className="animate-spin" aria-hidden />} {t("mkOnlineMake")}
          </Button>
        </div>
      )}
      {make.error && <p role="alert" className="text-destructive">{make.error.message}</p>}
    </div>
  );
}
