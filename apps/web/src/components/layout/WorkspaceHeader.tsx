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
        "rounded-md border border-[var(--workspace-border)] bg-[var(--workspace-surface)] px-5 py-5 shadow-[0_18px_44px_-32px_rgba(22,53,81,0.55)] sm:px-6",
        className,
      )}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="text-xs font-semibold uppercase text-primary">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="mt-2 text-2xl font-semibold text-foreground sm:text-3xl">
            {title}
          </h1>
          {description ? (
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
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
