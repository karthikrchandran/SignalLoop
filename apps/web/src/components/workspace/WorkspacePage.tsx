import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export type WorkspaceMetric = {
  label: string
  value: ReactNode
  hint?: string
  icon?: LucideIcon
  tone?: "default" | "success" | "info" | "warning"
}

const toneClass = {
  default:
    "bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400 border border-indigo-100/80 dark:border-indigo-800/40",
  success:
    "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400 border border-emerald-100/80 dark:border-emerald-800/40",
  info:
    "bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400 border border-blue-100/80 dark:border-blue-800/40",
  warning:
    "bg-amber-50 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400 border border-amber-100/80 dark:border-amber-800/40",
}

export function WorkspacePage({
  eyebrow,
  title,
  description,
  note,
  actions,
  icon: HeaderIcon,
  metrics,
  children,
}: {
  eyebrow?: string
  title: string
  description: string
  note?: string
  actions?: ReactNode
  icon?: LucideIcon
  metrics?: WorkspaceMetric[]
  children?: ReactNode
}) {
  return (
    <div className="space-y-4">
      <section className="workspace-page-header">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            {HeaderIcon ? (
              <span className="hidden size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary sm:flex">
                <HeaderIcon className="size-5" />
              </span>
            ) : null}
            <div className="min-w-0 space-y-0.5">
              {eyebrow ? (
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-primary">
                  {eyebrow}
                </p>
              ) : null}
              <h1 className="text-xl font-semibold leading-tight tracking-tight text-foreground">
                {title}
              </h1>
              <p className="max-w-3xl text-[13px] leading-snug text-muted-foreground">{description}</p>
              {note ? (
                <p className="max-w-3xl text-xs leading-snug text-muted-foreground/80">{note}</p>
              ) : null}
            </div>
          </div>
          {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      </section>
      {metrics && metrics.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {metrics.map((metric) => {
            const Icon = metric.icon
            return (
              <article key={metric.label} className="workspace-metric">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-medium text-muted-foreground">{metric.label}</p>
                  {Icon ? (
                    <span className={cn("rounded-md p-1.5", toneClass[metric.tone ?? "default"])}>
                      <Icon className="size-4" />
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-xl font-semibold leading-tight tracking-tight text-foreground tabular-nums">
                  {metric.value}
                </p>
                {metric.hint ? (
                  <p className="mt-0.5 text-[11px] font-medium text-muted-foreground">{metric.hint}</p>
                ) : null}
              </article>
            )
          })}
        </div>
      ) : null}
      {children}
    </div>
  )
}
