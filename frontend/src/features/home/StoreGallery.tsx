import { useRef, useState } from "react";
import { Search, X } from "lucide-react";

import type { ProjectListItem } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { NewStoreTile, StoreTile, StoreTileSkeleton } from "./StoreTile";

interface StoreGalleryProps {
  projects: ProjectListItem[] | undefined;
  isLoading: boolean;
  isFetching: boolean;
  error: unknown;
  onRetry: () => void;
  onOpen: (projectId: string) => void;
  onCreate: () => void;
}

function searchText(value: string) {
  return value.normalize("NFKC").toLowerCase().replace(/[_\s-]+/g, " ").trim();
}

export function StoreGallery({ projects, isLoading, isFetching, error, onRetry, onOpen, onCreate }: StoreGalleryProps) {
  const [filter, setFilter] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const query = searchText(filter);
  const shown = (projects ?? []).filter((p) =>
    searchText(`${p.name} ${p.store_type} ${p.description}`).includes(query),
  );
  const showSearch = (projects?.length ?? 0) > 0 || filter !== "";
  const clear = () => {
    setFilter("");
    if (projects?.length) input.current?.focus();
    else heading.current?.focus();
  };

  return (
    <section className="relative mx-auto max-w-7xl px-6 pt-6 pb-16" aria-labelledby="stores-heading">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">Workspace</div>
          <h2 id="stores-heading" ref={heading} tabIndex={-1} className="mt-1 font-display text-[2rem] leading-none outline-none">
            Your stores
            {projects && projects.length > 0 && <span className="num ml-3 align-middle text-base text-muted-foreground">{projects.length}</span>}
          </h2>
        </div>
        {showSearch && (
          <div className="glass flex h-10 w-full max-w-xs items-center gap-2 rounded-xl px-3 text-sm sm:w-72 focus-within:ring-2 focus-within:ring-ring">
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <input
              ref={input}
              type="search"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); clear(); } }}
              placeholder="Filter stores"
              className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground [&::-webkit-search-cancel-button]:appearance-none"
              aria-label="Filter stores"
              aria-describedby={query ? "store-filter-results" : undefined}
            />
            {filter && (
              <button type="button" className="grid size-7 shrink-0 place-items-center rounded-full hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring" aria-label="Clear store filter" onClick={clear}>
                <X className="size-3.5" aria-hidden />
              </button>
            )}
          </div>
        )}
      </div>

      {error != null && (
        <div role="alert" className="tone-bad mb-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4 text-sm">
          <span className="min-w-0 break-words">{error instanceof Error ? error.message : "Could not load stores"}</span>
          <Button size="sm" variant="outline" onClick={onRetry} disabled={isFetching}>
            {isFetching ? "Trying again…" : "Try again"}
          </Button>
        </div>
      )}

      {isLoading ? (
        <div role="status" aria-label="Loading stores" className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <StoreTileSkeleton key={i} />)}
        </div>
      ) : projects && (
        <>
          <p id="store-filter-results" role="status" className={query ? "mb-4 text-sm text-muted-foreground" : "sr-only"}>
            {query ? `${shown.length} of ${projects.length} stores` : `${projects.length} ${projects.length === 1 ? "store" : "stores"}`}
          </p>
          {query && shown.length === 0 ? (
            <div className="mb-5 flex flex-col items-center gap-3 rounded-2xl border border-dashed px-5 py-10 text-center">
              <Search className="size-6 text-muted-foreground" aria-hidden />
              <h3 className="text-lg font-medium">No matching stores</h3>
              <p className="text-sm text-muted-foreground">Try another name, format or description.</p>
              <Button variant="outline" onClick={clear}>Clear filter</Button>
            </div>
          ) : projects.length === 0 && error == null && (
            <p className="mb-5 text-sm text-muted-foreground">No stores yet. Create your first store from a furnished template.</p>
          )}
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {shown.map((p, i) => <StoreTile key={p.project_id} index={i} project={p} onOpen={() => onOpen(p.project_id)} />)}
            <NewStoreTile onClick={onCreate} />
          </div>
        </>
      )}
    </section>
  );
}
