import { cn } from '@/lib/utils'

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("bg-bg-tertiary rounded-[var(--radius-sm)] animate-pulse-skeleton", className)}
      {...props}
    />
  )
}
