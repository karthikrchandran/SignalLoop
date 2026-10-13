import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

type WorkspaceHeaderProps = {
  eyebrow?: string
  title: string
  description?: string
  actions?: ReactNode
  className?: string
}

export function WorkspaceHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: WorkspaceHeaderProps) {
  return (
    <section
      className={cn(
        "rounded-lg border border-[var(--workspace-border)] bg-[var(--workspace-surface)] px-5 py-4 shadow-xs",
        className,
      )}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-primary">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="text-xl font-semibold leading-tight text-foreground">
            {title}
          </h1>
          {description ? (
            <p className="mt-0.5 max-w-3xl text-[13px] leading-snug text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {actions}
          </div>
        ) : null}
      </div>
    </section>
  )
}

export default WorkspaceHeader
