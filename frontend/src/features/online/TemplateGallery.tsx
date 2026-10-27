// Pick a ready-made web shop (or the store's own shelves) to start an online store from.

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Search, Store } from "lucide-react";

import type { SetupSummary } from "@/shared/api/client";
import { createSite, FROM_STORE, onlineKeys, templatePreviewUrl, type OnlineTemplate } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import { searchText } from "@/shared/utils/searchText";

import { HIGHLIGHT_LABELS, templateDescriptionKey } from "./labels";

export function TemplateGallery({
  projectId, currency, templates, loading, error, setups, onCreated, onCancel,
}: {
  projectId: string;
  currency: string;
  templates: OnlineTemplate[];
  loading: boolean;
  error: string | null;
  setups: SetupSummary[];
  onCreated: (siteId: string) => void;
  onCancel?: () => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [chosen, setChosen] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [setupId, setSetupId] = useState("");
  const describe = (tpl: OnlineTemplate) => {
    const key = templateDescriptionKey(tpl.id);
    return key ? t(key) : tpl.description;
  };
  const shown = templates.filter((tpl) => {
    const words = searchText(query);
    return !words || searchText(`${tpl.name} ${tpl.vertical} ${tpl.description} ${describe(tpl)}`).includes(words);
  });
  const create = useMutation({
    mutationFn: () => createSite(projectId, {
      template_id: chosen!, name: name.trim() || undefined, setup_id: chosen === FROM_STORE ? setupId || null : null,
    }),
    onSuccess: (site) => {
      void qc.invalidateQueries({ queryKey: onlineKeys.sites(projectId) });
      onCreated(site.id);
    },
  });

  return (
    <section className="panel flex flex-col gap-4 rounded-[1.6rem] p-4" aria-labelledby="online-gallery">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="online-gallery" className="font-display text-2xl">{t("onGalleryTitle")}</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">{t("onGalleryBody", { count: templates.length })}</p>
        </div>
        {onCancel && <Button variant="outline" size="sm" onClick={onCancel}>{t("cancel")}</Button>}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          {/* Opened from "New online store" (it can be cancelled): start in the search, not back at that button. */}
          <Input className="pl-8" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("onGallerySearch")} aria-label={t("onGallerySearch")}
            autoFocus={!!onCancel} />
        </label>
      </div>

      {loading && <p className="text-sm text-muted-foreground">{t("studioLoading")}</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      <ul className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3">
        <li>
          <button type="button" onClick={() => setChosen(FROM_STORE)} aria-pressed={chosen === FROM_STORE}
            className={cn("flex h-full w-full flex-col gap-2 rounded-2xl border p-3 text-left transition-colors", chosen === FROM_STORE ? "border-primary ring-2 ring-primary/30" : "hover:bg-muted")}>
            <span className="grid aspect-[4/3] w-full place-items-center rounded-xl bg-muted"><Store className="size-10 text-primary" aria-hidden /></span>
            <span className="font-semibold">{t("onFromStore")}</span>
            <span className="text-xs text-muted-foreground">{t("onFromStoreBody")}</span>
          </button>
        </li>
        {shown.map((tpl) => (
          <li key={tpl.id}>
            <button type="button" onClick={() => setChosen(tpl.id)} aria-pressed={chosen === tpl.id}
              className={cn("flex h-full w-full flex-col gap-2 rounded-2xl border p-3 text-left transition-colors", chosen === tpl.id ? "border-primary ring-2 ring-primary/30" : "hover:bg-muted")}>
              <span className="block aspect-[4/3] w-full overflow-hidden rounded-xl border bg-muted">
                <img src={templatePreviewUrl(tpl.id, currency)} alt="" loading="lazy" className="w-full object-cover object-top" />
              </span>
              <span className="flex items-center gap-2 font-semibold">
                <span className="size-3 shrink-0 rounded-full ring-1 ring-foreground/25 dark:ring-foreground/55" style={{ background: tpl.theme_color }} aria-hidden />{tpl.name}
              </span>
              <span className="text-xs text-muted-foreground">{describe(tpl)}</span>
              <span className="text-xs text-muted-foreground">{t("onTplStats", { products: tpl.products, photos: tpl.photos, categories: tpl.categories })}</span>
              {tpl.highlights.length > 0 && (
                <span className="flex flex-wrap gap-1">
                  {tpl.highlights.map((h) => <span key={h} className="rounded-full bg-primary/10 px-2 py-0.5 text-[0.7rem] text-primary">{t(HIGHLIGHT_LABELS[h])}</span>)}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
      {!loading && shown.length === 0 && <p role="status" className="text-sm text-muted-foreground">{t("onGalleryNone")}</p>}

      {chosen && (
        <div className="sticky bottom-0 flex flex-wrap items-end gap-3 rounded-2xl border bg-card p-3 shadow-lg">
          <label className="flex min-w-0 flex-1 basis-40 flex-col gap-1 text-xs">
            <span className="text-muted-foreground">{t("onStoreName")}</span>
            <Input value={name} maxLength={60} onChange={(e) => setName(e.target.value)}
              placeholder={chosen === FROM_STORE ? t("onFromStore") : templates.find((tpl) => tpl.id === chosen)?.name} />
          </label>
          {chosen === FROM_STORE && (
            <label className="flex min-w-0 flex-1 basis-40 flex-col gap-1 text-xs">
              <span className="text-muted-foreground">{t("onFromLayout")}</span>
              <select className="h-9 rounded-md border bg-background px-2 text-sm" value={setupId} onChange={(e) => setSetupId(e.target.value)}>
                <option value="">{t("onActiveLayout")}</option>
                {setups.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
          )}
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            {create.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />} {t("onCreateStore")}
          </Button>
          {create.error && <p role="alert" className="w-full text-xs text-destructive">{create.error.message}</p>}
        </div>
      )}
    </section>
  );
}
