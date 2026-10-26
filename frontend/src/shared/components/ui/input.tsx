import * as React from "react"

import { cn } from "@/shared/utils/cn"
import { useI18n } from "@/shared/i18n/i18n"

// The browser draws its own "Choose File / No file chosen" in the browser's language, not the app's. The real input
// still takes the click (invisible, over the whole field) and the keyboard focus; the words come from the catalog.
function FileInput({ className, onChange, disabled, ...props }: Omit<React.ComponentProps<"input">, "type">) {
  const { t } = useI18n()
  const [names, setNames] = React.useState("")
  return (
    <span data-slot="input" className={cn(
      "relative flex h-10 w-full min-w-0 items-center gap-3 rounded-xl border border-input bg-card/60 px-1.5 text-sm transition-[border-color,box-shadow] duration-200 hover:border-foreground/20 focus-within:border-ring focus-within:ring-4 focus-within:ring-ring/20 dark:bg-white/[0.03]",
      disabled && "pointer-events-none opacity-50",
      className
    )}>
      <input type="file" disabled={disabled} className="absolute inset-0 size-full cursor-pointer opacity-0" {...props}
        onChange={(event) => { setNames(Array.from(event.target.files ?? [], (file) => file.name).join(", ")); onChange?.(event) }} />
      {/* Drawn as CSS content, so a wrapping label's text (the field's name) stays only its own words. */}
      <span aria-hidden data-text={t("fileChoose")}
        className="inline-flex h-7 shrink-0 items-center rounded-lg bg-foreground/[0.07] px-3 font-medium text-foreground before:content-[attr(data-text)]" />
      <span aria-hidden data-text={names || t("fileNone")} className="min-w-0 truncate text-muted-foreground before:content-[attr(data-text)]" />
    </span>
  )
}

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  if (type === "file") return <FileInput className={className} {...props} />
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-10 w-full min-w-0 rounded-xl border border-input bg-card/60 px-3.5 py-1 text-base shadow-[inset_0_1px_2px_rgb(0_0_0/0.04)] transition-[border-color,box-shadow,background-color] duration-200 hover:border-foreground/20 outline-none file:mr-3 file:inline-flex file:h-7 file:cursor-pointer file:items-center file:rounded-lg file:border-0 file:bg-foreground/[0.07] file:px-3 file:text-sm file:font-medium file:text-foreground hover:file:bg-foreground/[0.12] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:bg-card focus-visible:ring-4 focus-visible:ring-ring/20 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-white/[0.03] dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
        className
      )}
      {...props}
    />
  )
}

export { Input }
