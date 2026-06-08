import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { BotSettingsPage } from "@/features/chatbot"
import { isChatbotDemoMode } from "@/features/chatbot/demo"

type UserWithRole = {
  is_superuser?: boolean
  role?: string | null
}

const isAdmin = (user: UserWithRole) =>
  Boolean(user.is_superuser || user.role === "admin" || user.role === "super_admin")

export const Route = createFileRoute("/_layout/chatbot/settings")({
  component: BotSettingsPage,
  beforeLoad: async () => {
    if (isChatbotDemoMode()) return
    const user = await UsersService.readUserMe() as UserWithRole
    if (!isAdmin(user)) {
      throw redirect({ to: "/chatbot/inbox" })
    }
  },
  head: () => ({
    meta: [{ title: "Messaging Hub Settings - EngageHub" }],
  }),
})
