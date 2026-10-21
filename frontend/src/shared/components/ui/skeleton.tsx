import { cn } from "@/shared/utils/cn"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("shimmer rounded-xl bg-foreground/[0.06]", className)}
      {...props}
    />
  )
}

export { Skeleton }
