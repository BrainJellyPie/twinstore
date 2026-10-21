import type { ReactNode } from "react";

import { LayoutTabs } from "@/features/layouts/components/LayoutTabs";
import type { Layout } from "@/features/layouts/hooks/useLayouts";

export interface ProjectShellProps {
  layouts: Layout[];
  selectedLayoutId: string | null;
  onLayoutSelect: (id: string) => void;
  onAddLayout: () => void;
  centerSlot: ReactNode;
  footerSlot?: ReactNode;
  sidePanelSlot: ReactNode;
  navigationDisabled?: boolean;
}

export function ProjectShell({
  layouts,
  selectedLayoutId,
  onLayoutSelect,
  onAddLayout,
  centerSlot,
  footerSlot,
  sidePanelSlot,
  navigationDisabled = false,
}: ProjectShellProps) {
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto md:flex-row md:overflow-hidden">
      <div className="m-3 flex min-h-0 min-w-0 shrink-0 flex-col gap-3 md:mr-0 md:flex-1 md:overflow-y-auto">
        <div className="relative h-[60dvh] min-h-96 shrink-0 overflow-hidden rounded-[1.6rem] border border-glass-border shadow-[var(--shadow-lift)] md:h-auto md:flex-1">
          {layouts.length > 0 && (
            <div className="pointer-events-auto absolute left-3 top-3 z-10 max-w-[calc(100%-1.5rem)] xl:max-w-[calc(100%-27rem)]">
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
        {footerSlot}
      </div>
      {sidePanelSlot}
    </div>
  );
}
