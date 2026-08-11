import { createFileRoute, Outlet, redirect, useRouterState } from "@tanstack/react-router"

import { type UserPublic, UsersService } from "@/client"
import { PlatformAdminLayout } from "@/features/admin/PlatformAdminLayout"

type UserWithRole = UserPublic & { role?: string | null }

export const Route = createFileRoute("/_layout/platform")({
  component: PlatformAdmin,
  beforeLoad: async () => {
    const user = (await UsersService.readUserMe()) as UserWithRole
    if (!user.is_superuser && user.role !== "platform_admin") {
      throw redirect({ to: "/" })
    }
  },
})

function PlatformAdmin() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  if (pathname !== "/platform") return <Outlet />
  return <PlatformAdminLayout />
}
