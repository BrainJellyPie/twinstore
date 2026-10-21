import * as React from "react"

import { cn } from "@/shared/utils/cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-20 w-full rounded-xl border border-input bg-card/60 px-3.5 py-2.5 text-base shadow-[inset_0_1px_2px_rgb(0_0_0/0.04)] transition-[border-color,box-shadow,background-color] duration-200 hover:border-foreground/20 outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:bg-card focus-visible:ring-4 focus-visible:ring-ring/20 disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-white/[0.03] dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
