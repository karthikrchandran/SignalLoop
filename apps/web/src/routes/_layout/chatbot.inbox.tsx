import { createFileRoute } from "@tanstack/react-router"

import { InboxPage } from "@/features/chatbot"

export const Route = createFileRoute("/_layout/chatbot/inbox")({
  component: InboxPage,
  head: () => ({
    meta: [{ title: "Messaging Hub Inbox - SignalLoop" }],
  }),
})
