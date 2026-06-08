import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { DeadLettersPage } from "@/features/chatbot"
import { isChatbotDemoMode } from "@/features/chatbot/demo"

type UserWithRole = {
  is_superuser?: boolean
  role?: string | null
}

const isOperator = (user: UserWithRole) =>
  Boolean(user.is_superuser || user.role === "operator" || user.role === "super_admin")

export const Route = createFileRoute("/_layout/admin/chatbot/dead-letters")({
  component: DeadLettersPage,
  beforeLoad: async () => {
    if (isChatbotDemoMode()) return
    const user = await UsersService.readUserMe() as UserWithRole
    if (!isOperator(user)) {
      throw redirect({ to: "/chatbot/inbox" })
    }
  },
  head: () => ({
    meta: [{ title: "Messaging Dead Letters - EngageHub" }],
  }),
})
