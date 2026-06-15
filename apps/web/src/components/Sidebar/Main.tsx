import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import type { LucideIcon } from "lucide-react"

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export type Item = {
  icon: LucideIcon
  title: string
  path: string
  badge?: number
}

export type ItemGroup = {
  title?: string
  items: Item[]
}

interface MainProps {
  items?: Item[]
  groups?: ItemGroup[]
}

export function Main({ items = [], groups }: MainProps) {
  const { isMobile, setOpenMobile } = useSidebar()
  const router = useRouterState()
  const currentPath = router.location.pathname
  const visibleGroups = groups ?? [{ items }]

  const handleMenuClick = () => {
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  return (
    <>
      {visibleGroups.map((group, index) => (
        <SidebarGroup
          key={group.title ?? `sidebar-group-${index}`}
          className="px-2 py-1"
        >
          {group.title ? (
            <SidebarGroupLabel className="h-7 px-2 text-[0.7rem] font-semibold uppercase text-sidebar-foreground/55">
              {group.title}
            </SidebarGroupLabel>
          ) : null}
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              {group.items.map((item) => {
                const isActive = currentPath === item.path || currentPath.startsWith(`${item.path}/`)

                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      tooltip={item.title}
                      isActive={isActive}
                      asChild
                      className="h-9 rounded-md text-sidebar-foreground/78 hover:bg-white/10 hover:text-white data-[active=true]:bg-white/16 data-[active=true]:text-white data-[active=true]:shadow-[inset_3px_0_0_var(--sidebar-primary)]"
                    >
                      <RouterLink
                        to={item.path}
                        onClick={handleMenuClick}
                        aria-current={isActive ? "page" : undefined}
                      >
                        <item.icon />
                        <span>{item.title}</span>
                      </RouterLink>
                    </SidebarMenuButton>
                    {item.badge ? (
                      <SidebarMenuBadge className="text-sidebar-foreground/70">
                        {item.badge}
                      </SidebarMenuBadge>
                    ) : null}
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      ))}
    </>
  )
}
