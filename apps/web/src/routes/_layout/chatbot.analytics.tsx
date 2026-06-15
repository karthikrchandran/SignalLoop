import { createFileRoute } from "@tanstack/react-router"

import { AnalyticsPage } from "@/features/chatbot"

export const Route = createFileRoute("/_layout/chatbot/analytics")({
  component: AnalyticsPage,
  head: () => ({
    meta: [{ title: "Messaging Hub Analytics - SignalLoop" }],
  }),
})
