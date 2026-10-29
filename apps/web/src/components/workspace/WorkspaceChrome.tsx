import { useRouterState } from "@tanstack/react-router"
import { ChevronRight } from "lucide-react"

import { SidebarTrigger } from "@/components/ui/sidebar"
import { resolveWorkspaceLocation } from "@/components/workspace/workspace-routes"

export function WorkspaceChrome() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const location = resolveWorkspaceLocation(pathname)

  return (
    <header className="workspace-command sticky top-0 z-20 border-b">
      <div className="flex h-11 items-center gap-3 px-4 sm:px-5 lg:px-6">
        <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground" />
        <nav
          aria-label="Workspace location"
          className="flex min-w-0 items-center gap-1.5 text-sm"
        >
          <span className="hidden font-medium text-muted-foreground sm:inline">
            SignalLoop
          </span>
          <ChevronRight className="hidden size-3.5 text-muted-foreground/70 sm:inline" />
          <span className="text-muted-foreground">{location.section}</span>
          <ChevronRight className="size-3.5 text-muted-foreground/70" />
          <span className="truncate font-medium text-foreground">
            {location.title}
          </span>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
            <span className="size-1.5 rounded-full bg-[var(--workspace-success)]" />
            Live workspace
          </span>
        </div>
      </div>
    </header>
  )
}
