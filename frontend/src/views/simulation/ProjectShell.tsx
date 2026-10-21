import type { ReactNode } from "react";

import { LayoutTabs } from "@/features/layouts/components/LayoutTabs";
import type { Layout } from "@/features/layouts/hooks/useLayouts";

export interface ProjectShellProps {
  layouts: Layout[];
  selectedLayoutId: string | null;
  onLayoutSelect: (id: string) => void;
  onAddLayout: () => void;
  centerSlot: ReactNode;
  sidePanelSlot: ReactNode;
  navigationDisabled?: boolean;
}

export function ProjectShell({
  layouts,
  selectedLayoutId,
  onLayoutSelect,
  onAddLayout,
  centerSlot,
  sidePanelSlot,
  navigationDisabled = false,
}: ProjectShellProps) {
  return (
    <>
      <div className="relative m-3 mr-0 flex-1 overflow-hidden rounded-[1.6rem] border border-glass-border shadow-[var(--shadow-lift)]">
        {layouts.length > 0 && (
          <div className="pointer-events-auto absolute left-3 top-3 z-10 max-w-[calc(100%-1.5rem)] lg:max-w-[calc(100%-27rem)]">
            <LayoutTabs
              layouts={layouts}
              selectedId={selectedLayoutId ?? undefined}
              onSelect={onLayoutSelect}
              onAddNew={onAddLayout}
              disabled={navigationDisabled}
            />
          </div>
        )}
        {centerSlot}
      </div>
      {sidePanelSlot}
    </>
  );
}
