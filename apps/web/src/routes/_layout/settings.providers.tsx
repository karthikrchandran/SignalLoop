import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import ProviderSetupPage from "@/features/providers/ProviderSetupPage"

export const Route = createFileRoute("/_layout/settings/providers")({
  component: ProviderSetupPage,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Provider Setup - SignalLoop",
      },
    ],
  }),
})
